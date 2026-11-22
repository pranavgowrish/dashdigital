import base64
import math
import os
import subprocess
import tempfile
import uuid
from pathlib import Path
import numpy as np
import requests
from PIL import Image
from scipy.ndimage import map_coordinates
from .merge_splats import merge_splats, GSV_PITCH_DOWN_DEG

GSV_HEADINGS = [0, 90, 180, 270]  # heading=0 is True North, so the panorama's own heading is 0.0
GSV_SIZE = "640x640"
GSV_FOV_DEG = 95
GSV_PITCH_DEG = -GSV_PITCH_DOWN_DEG

# VIOFO A119 Mini 2, keep in sync with backend.py: 140 deg diagonal equidistant fisheye (r = f * theta),
# mounted 3.8 deg down and 4.3 deg left of the car's direction of travel.
DASHCAM_DIAG_FOV_DEG = 140.0
DASHCAM_PITCH_DOWN_DEG = 3.8
DASHCAM_YAW_LEFT_DEG = 4.3
# The level view handed to SHARP stops this far below the horizon, just above the hood
# (the hood's top edge sits about 19 deg down), so the hood and the HUD text are cropped out.
DASHCAM_VIEW_BELOW_DEG = 17.0
DASHCAM_VIEW_ABOVE_DEG = 17.0

SHARP_DEVICE = "mps"
SHARP_BIN = Path(__file__).parent.parent / ".venv" / "bin" / "sharp"  # ml-sharp submodule installed into backend/.venv
OUTPUT_DIR = Path(__file__).parent / "out"

# SHARP_RUNNER in .env picks where SHARP runs: "local" (this Mac, MPS) or "cluster" (CUDA over ssh).
# The cluster side is set up once with 3dgs/setup_cluster.sh.
SHARP_REMOTE_HOST = "pgowr001@crisgc.engr.ucr.edu"
SHARP_REMOTE_HOME = "~/dashdigital-sharp"           # venv + ml-sharp live here; jobs/ holds per-request dirs
# crisgc is a login node: SLURM puts the job on a GPU in the cisl partition (dune1/dune2, RTX 6000 Ada).
SHARP_REMOTE_LAUNCHER = "srun --unbuffered -p cisl --gres=gpu:1 -c 8 --mem=32G -t 30"
# Reuse one ssh connection for every call (the cluster bans hosts that open too many), and fail
# instead of hanging on a password prompt the backend can't answer.
SSH_OPTS = [
    "-o", "BatchMode=yes",
    "-o", "ControlMaster=auto",
    "-o", "ControlPath=~/.ssh/cm-%r@%h:%p",
    "-o", "ControlPersist=4h",
]

DIAG_35MM = math.hypot(36.0, 24.0)  # 43.267 mm, the 35mm-film diagonal SHARP normalizes to
CROP_GUESS = 8.4                    # ml-sharp's crude multiplier for a sub-10mm FocalLength
EXIF_IFD = 0x8769
TAG_FOCAL_LENGTH = 0x920A           # FocalLength (RATIONAL, so it keeps fractions)
TAG_FOCAL_35MM = 0xA405             # FocalLengthIn35mmFilm (SHORT; SHARP prefers this one)

def f_35mm_from_fov(image_path, fov_deg):
    with Image.open(image_path) as im:
        width, height = im.size

    f_px = (width / 2) / math.tan(math.radians(fov_deg) / 2)

    return f_px * DIAG_35MM / math.hypot(width, height)

def level_dashcam_view(src, dst):
    # SHARP assumes an undistorted photo with the principal point in the middle. Resample the
    # fisheye frame into a pinhole view that is level and faces the car's direction of travel,
    # so the merge only has to turn it to the car's heading. Returns the view's horizontal FOV.
    with Image.open(src) as im:
        frame = np.asarray(im.convert("RGB"), dtype=np.float32)
    height, width = frame.shape[:2]
    # Frames are 16:9; a screenshot may be trimmed at the bottom, so the centre comes from the width.
    cx, cy = width / 2, width * 9 / 32
    f = math.hypot(cx, cy) / math.radians(DASHCAM_DIAG_FOV_DEG / 2)

    # Output pinhole camera: same focal length, so the centre keeps its resolution.
    out_h = round(f * math.tan(math.radians(DASHCAM_VIEW_ABOVE_DEG))), round(f * math.tan(math.radians(DASHCAM_VIEW_BELOW_DEG)))
    ys, xs = np.mgrid[-out_h[0]:out_h[1], 0:width].astype(np.float32)
    rays = np.stack([(xs - cx) / f, ys / f, np.ones_like(xs)], axis=-1)

    # Level, car-forward axes expressed in the real camera's axes (x right, y down, z forward).
    pitch, yaw = math.radians(DASHCAM_PITCH_DOWN_DEG), math.radians(DASHCAM_YAW_LEFT_DEG)
    forward = np.array([math.sin(yaw) * math.cos(pitch), -math.sin(pitch), math.cos(yaw) * math.cos(pitch)])
    down = np.array([math.sin(yaw) * math.sin(pitch), math.cos(pitch), math.cos(yaw) * math.sin(pitch)])
    right = np.cross(down, forward)
    cam = rays @ np.stack([right, down, forward])
    cam /= np.linalg.norm(cam, axis=-1, keepdims=True)

    # Fisheye projection back into the source frame.
    theta = np.arccos(np.clip(cam[..., 2], -1, 1))
    r_xy = np.maximum(np.hypot(cam[..., 0], cam[..., 1]), 1e-9)
    u = cx + f * theta * cam[..., 0] / r_xy
    v = cy + f * theta * cam[..., 1] / r_xy
    out = np.stack([map_coordinates(frame[..., c], [v, u], order=1, mode="nearest") for c in range(3)], axis=-1)

    Image.fromarray(out.clip(0, 255).astype(np.uint8)).save(dst, quality=97)
    return math.degrees(2 * math.atan(width / 2 / f))

def stage_with_focal(src, f_35mm, stage_dir):
    # Copy the photo with its EXIF focal length rewritten, so SHARP reads our value.
    # We write FocalLength rather than FocalLengthIn35mmFilm: the latter is an integer
    # EXIF type, which would quantize the field of view. FocalLength is rational, but
    # ml-sharp only trusts it when it's >= 10mm and multiplies anything smaller by 8.4,
    # so pre-divide in that case and let SHARP's own multiplier undo it.
    stored = f_35mm if f_35mm >= 10.0 else f_35mm / CROP_GUESS

    with Image.open(src) as im:
        im = im.convert("RGB")
        exif = im.getexif()
        exif.pop(TAG_FOCAL_35MM, None)  # else it would take priority over FocalLength
        exif.get_ifd(EXIF_IFD).pop(TAG_FOCAL_35MM, None)
        exif.get_ifd(EXIF_IFD)[TAG_FOCAL_LENGTH] = stored
        out = stage_dir / f"{src.stem}.jpg"
        im.save(out, "JPEG", quality=97, subsampling=0, exif=exif)

    return out

def fetch_street_view(car_lat, car_lon, image_dir):
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")

    metadata = requests.get(
        "https://maps.googleapis.com/maps/api/streetview/metadata",
        params={"location": f"{car_lat},{car_lon}", "key": api_key},
        timeout=30,
    ).json()

    if metadata["status"] != "OK":
        raise ValueError(f"No Street View panorama near {car_lat},{car_lon}: {metadata['status']}")

    for heading in GSV_HEADINGS:
        response = requests.get(
            "https://maps.googleapis.com/maps/api/streetview",
            params={
                "size": GSV_SIZE,
                "pano": metadata["pano_id"],
                "heading": heading,
                "fov": GSV_FOV_DEG,
                "pitch": GSV_PITCH_DEG,
                "return_error_code": "true",
                "key": api_key,
            },
            timeout=30,
        )

        # Not raise_for_status(): its message includes the URL, and so the API key.
        if response.status_code != 200:
            raise ValueError(f"Street View image at heading {heading} failed: {response.status_code}")

        (image_dir / f"gsv_{heading}.jpg").write_bytes(response.content)

    return metadata["location"]["lat"], metadata["location"]["lng"]

def run_sharp(input_dir, output_dir):
    runner = os.getenv("SHARP_RUNNER", "local").lower()
    if runner == "cluster":
        return run_sharp_cluster(input_dir, output_dir)
    if runner != "local":
        raise ValueError(f"SHARP_RUNNER must be 'local' or 'cluster', not {runner!r}")

    # One batch call so the model loads once. The checkpoint auto-downloads and caches unless SHARP_CHECKPOINT is set.
    cmd = [os.getenv("SHARP_BIN", str(SHARP_BIN)), "predict", "-i", str(input_dir), "-o", str(output_dir), "--device", SHARP_DEVICE]

    if os.getenv("SHARP_CHECKPOINT"):
        cmd += ["-c", os.getenv("SHARP_CHECKPOINT")]

    subprocess.run(cmd, check=True)

def ssh(host, command, **kwargs):
    return subprocess.run(["ssh", *SSH_OPTS, host, command], check=True, **kwargs)

def run_sharp_cluster(input_dir, output_dir):
    # Same `sharp predict`, on the cluster's GPU. Images go up and .ply files come back as tar
    # streams over the shared ssh connection; SHARP's log streams straight to this terminal.
    host = os.getenv("SHARP_REMOTE_HOST", SHARP_REMOTE_HOST)
    home = os.getenv("SHARP_REMOTE_HOME", SHARP_REMOTE_HOME)
    launcher = os.getenv("SHARP_REMOTE_LAUNCHER", SHARP_REMOTE_LAUNCHER)
    job = f"{home}/jobs/{uuid.uuid4().hex}"

    print(f"[sharp] running on {host} ({job})", flush=True)
    ssh(host, f"mkdir -p {job}/input {job}/output")
    try:
        with subprocess.Popen(["tar", "-C", str(input_dir), "-cf", "-", "."], stdout=subprocess.PIPE) as upload:
            ssh(host, f"tar -C {job}/input -xf -", stdin=upload.stdout)
        if upload.returncode:
            raise RuntimeError("Packing the SHARP inputs failed")

        cmd = f"{launcher} {home}/.venv/bin/sharp predict -i {job}/input -o {job}/output --device cuda"
        if os.getenv("SHARP_REMOTE_CHECKPOINT"):
            cmd += f" -c {os.getenv('SHARP_REMOTE_CHECKPOINT')}"
        ssh(host, cmd)

        with subprocess.Popen(["tar", "-C", str(output_dir), "-xf", "-"], stdin=subprocess.PIPE) as download:
            ssh(host, f"tar -C {job}/output -cf - .", stdout=download.stdin)
            download.stdin.close()
        if download.returncode:
            raise RuntimeError("Unpacking the SHARP outputs failed")
    finally:
        ssh(host, f"rm -rf {job}")
    print(f"[sharp] done on {host}", flush=True)

def render_gaussian_splat(car_lat, car_lon, heading_deg, image_base64):
    # image_base64 must be the full dashcam frame (not a crop): its geometry is what places the splat.
    with tempfile.TemporaryDirectory(prefix="dashdigital-3dgs-") as temp_dir:
        image_dir = Path(temp_dir) / "images"
        input_dir = Path(temp_dir) / "input"
        output_dir = Path(temp_dir) / "output"
        image_dir.mkdir()
        input_dir.mkdir()
        output_dir.mkdir()

        pano_lat, pano_lon = fetch_street_view(car_lat, car_lon, image_dir)

        frame_path = image_dir / "frame.jpg"
        frame_path.write_bytes(base64.b64decode(image_base64))
        pothole_path = image_dir / "pothole.jpg"
        dashcam_hfov_deg = level_dashcam_view(frame_path, pothole_path)

        # Street View images carry no EXIF, so SHARP would assume 30mm (~65 deg) and warp the 95 deg views.
        for heading in GSV_HEADINGS:
            gsv_path = image_dir / f"gsv_{heading}.jpg"
            stage_with_focal(gsv_path, f_35mm_from_fov(gsv_path, GSV_FOV_DEG), input_dir)

        stage_with_focal(pothole_path, f_35mm_from_fov(pothole_path, dashcam_hfov_deg), input_dir)

        run_sharp(input_dir, output_dir)

        OUTPUT_DIR.mkdir(exist_ok=True)
        output_path = OUTPUT_DIR / f"{car_lat}_{car_lon}.ply"

        merge_splats(
            {heading: output_dir / f"gsv_{heading}.ply" for heading in GSV_HEADINGS},
            output_dir / "pothole.ply",
            pano_lat,
            pano_lon,
            car_lat,
            car_lon,
            heading_deg,
            output_path,
        )

    return output_path
