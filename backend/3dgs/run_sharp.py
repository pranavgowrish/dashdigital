import base64
import math
import os
import subprocess
import tempfile
from pathlib import Path
import requests
from PIL import Image
from .merge_splats import merge_splats, GSV_PITCH_DOWN_DEG

GSV_HEADINGS = [0, 90, 180, 270]  # heading=0 is True North, so the panorama's own heading is 0.0
GSV_SIZE = "640x640"
GSV_FOV_DEG = 95
GSV_PITCH_DEG = -GSV_PITCH_DOWN_DEG

# Used only when the pothole photo has no EXIF focal length and no FOV is passed in.
DASHCAM_FOV_DEG = 105.0

SHARP_DEVICE = "mps"
SHARP_BIN = Path(__file__).parent / ".venv" / "bin" / "sharp"  # ml-sharp submodule installed into 3dgs/.venv
OUTPUT_DIR = Path(__file__).parent / "out"

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

def exif_focal_35mm(image_path):
    # Mirrors ml-sharp's sharp/utils/io.py:load_rgb EXIF logic, minus its 30mm fallback.
    with Image.open(image_path) as im:
        exif = im.getexif()
        tags = dict(exif)
        tags.update(exif.get_ifd(EXIF_IFD))

    f_35mm = tags.get(TAG_FOCAL_35MM)
    if f_35mm is not None and float(f_35mm) >= 1:
        return float(f_35mm)

    f = tags.get(TAG_FOCAL_LENGTH)
    if not f:
        return None

    f = float(f)
    return f * CROP_GUESS if f < 10.0 else f

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
    # One batch call so the model loads once. The checkpoint auto-downloads and caches unless SHARP_CHECKPOINT is set.
    cmd = [os.getenv("SHARP_BIN", str(SHARP_BIN)), "predict", "-i", str(input_dir), "-o", str(output_dir), "--device", SHARP_DEVICE]

    if os.getenv("SHARP_CHECKPOINT"):
        cmd += ["-c", os.getenv("SHARP_CHECKPOINT")]

    subprocess.run(cmd, check=True)

def render_gaussian_splat(car_lat, car_lon, heading_deg, image_base64, dashcam_fov_deg=None):
    with tempfile.TemporaryDirectory(prefix="dashdigital-3dgs-") as temp_dir:
        image_dir = Path(temp_dir) / "images"
        input_dir = Path(temp_dir) / "input"
        output_dir = Path(temp_dir) / "output"
        image_dir.mkdir()
        input_dir.mkdir()
        output_dir.mkdir()

        pano_lat, pano_lon = fetch_street_view(car_lat, car_lon, image_dir)

        pothole_path = image_dir / "pothole.jpg"
        pothole_path.write_bytes(base64.b64decode(image_base64))

        # Street View images carry no EXIF, so SHARP would assume 30mm (~65 deg) and warp the 95 deg views.
        for heading in GSV_HEADINGS:
            gsv_path = image_dir / f"gsv_{heading}.jpg"
            stage_with_focal(gsv_path, f_35mm_from_fov(gsv_path, GSV_FOV_DEG), input_dir)

        pothole_f_35mm = exif_focal_35mm(pothole_path)
        if dashcam_fov_deg is not None or pothole_f_35mm is None:
            pothole_f_35mm = f_35mm_from_fov(pothole_path, dashcam_fov_deg or DASHCAM_FOV_DEG)
        stage_with_focal(pothole_path, pothole_f_35mm, input_dir)

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
