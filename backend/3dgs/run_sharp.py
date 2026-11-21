#!/usr/bin/env python3
"""One pothole photo -> a 3D Gaussian Splat .ply, via Apple's SHARP (apple/ml-sharp).

    python run_sharp.py photos/pothole.jpg
    python run_sharp.py photos/pothole.jpg --fov-deg 70        # phone-ish wide lens
    python run_sharp.py photos/pothole.jpg --focal-35mm 26
    python run_sharp.py photos/pothole.jpg -o out --device mps

SHARP does the reconstruction; this script is the thin part around it:

  1. it tells you the focal length SHARP will assume for your photo, and
  2. lets you override it, by restamping the photo's EXIF focal length.

That matters because SHARP infers metric 3D from a single image, so the assumed
field of view sets the pothole's depth and scale. With no focal length in EXIF,
SHARP silently falls back to 30 mm (see `effective_focal_35mm` below, which
mirrors ml-sharp's `sharp/utils/io.py:load_rgb`).

Output is <output dir>/<photo stem>.ply, in SHARP's OpenCV camera frame
(x right, y down, z forward), metric, with the scene roughly at (0, 0, +z).
View it with:  python -m http.server 8000   ->   localhost:8000/viewer/sharp.html
"""

from __future__ import annotations

import argparse
import math
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

DIAG_35MM = math.hypot(36.0, 24.0)  # 43.267 mm, the 35mm-film diagonal SHARP normalizes to
CROP_GUESS = 8.4                    # ml-sharp's crude multiplier for a sub-10mm FocalLength
DEFAULT_F_35MM = 30.0               # ml-sharp's fallback when EXIF has no focal length
EXIF_IFD = 0x8769
TAG_FOCAL_LENGTH = 0x920A           # FocalLength (RATIONAL, so it keeps fractions)
TAG_FOCAL_35MM = 0xA405             # FocalLengthIn35mmFilm (SHORT; SHARP prefers this one)

# Matches ml-sharp's get_supported_image_extensions() for the formats you'd realistically use.
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".tif", ".tiff", ".bmp", ".webp"}


def _load_pil():
    try:
        from PIL import Image
    except ImportError:
        sys.exit("Pillow is required: pip install -r requirements.txt")
    try:  # so --fov-deg/--focal-* also work on iPhone .heic originals
        import pillow_heif

        pillow_heif.register_heif_opener()
    except ImportError:
        pass
    return Image


def f_px_from_35mm(f_35mm: float, width: int, height: int) -> float:
    """ml-sharp's convert_focallength(): mm on 35mm film -> pixels for this image."""
    return f_35mm * math.hypot(width, height) / DIAG_35MM


def f_35mm_from_f_px(f_px: float, width: int, height: int) -> float:
    """Inverse of the above, so we can ask SHARP for an exact pixel focal length."""
    return f_px * DIAG_35MM / math.hypot(width, height)


def effective_focal_35mm(path: Path) -> tuple[float, int, int, str]:
    """What SHARP will assume for this photo. Mirrors ml-sharp io.load_rgb's EXIF logic."""
    Image = _load_pil()
    with Image.open(path) as im:
        width, height = im.size
        exif = im.getexif()
        tags = dict(exif)
        tags.update(exif.get_ifd(EXIF_IFD))

    f_35mm = tags.get(TAG_FOCAL_35MM)
    if f_35mm is not None and float(f_35mm) >= 1:
        return float(f_35mm), width, height, "EXIF FocalLengthIn35mmFilm"

    f = tags.get(TAG_FOCAL_LENGTH)
    if f is None:
        return DEFAULT_F_35MM, width, height, "no EXIF focal length -> ml-sharp's 30mm default"
    f = float(f)
    if f < 10.0:  # ml-sharp assumes a value this small is a real (non-35mm) focal length
        return f * CROP_GUESS, width, height, f"EXIF FocalLength {f:g}mm x{CROP_GUESS} crop guess"
    return f, width, height, "EXIF FocalLength (already 35mm-equivalent)"


def stage_with_focal(src: Path, f_35mm: float, stage_dir: Path) -> Path:
    """Copy the photo with its EXIF focal length rewritten, so SHARP reads our value.

    We write FocalLength rather than FocalLengthIn35mmFilm: the latter is an integer
    EXIF type, which would quantize the field of view. FocalLength is rational, but
    ml-sharp only trusts it when it's >= 10mm and multiplies anything smaller by 8.4 --
    so pre-divide in that case and let SHARP's own multiplier undo it.
    """
    Image = _load_pil()
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


def ply_gaussian_count(path: Path) -> int | None:
    """Read 'element vertex N' out of the .ply header."""
    try:
        with path.open("rb") as f:
            for _ in range(60):
                line = f.readline().decode("latin-1").strip()
                if not line or line == "end_header":
                    break
                if line.startswith("element vertex"):
                    return int(line.split()[-1])
    except OSError:
        pass
    return None


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("photo", type=Path, help="the pothole photo")
    ap.add_argument("-o", "--out", type=Path, default=Path("out"), help="output dir (default: out)")

    lens = ap.add_mutually_exclusive_group()
    lens.add_argument("--fov-deg", type=float, help="horizontal field of view of the photo")
    lens.add_argument("--focal-35mm", type=float, help="focal length in 35mm-equivalent mm")
    lens.add_argument("--focal-px", type=float, help="focal length in pixels of this photo")

    ap.add_argument("--device", choices=("default", "cpu", "mps", "cuda"), default="default",
                    help="default picks cuda, else mps (Apple Silicon), else cpu")
    ap.add_argument("-c", "--checkpoint", type=Path,
                    help="SHARP .pt checkpoint (default: auto-download + cache)")
    ap.add_argument("--render", action="store_true", help="also render an orbit mp4 (CUDA only)")
    ap.add_argument("--sharp-bin", default="sharp", help="the SHARP CLI (default: sharp on PATH)")
    ap.add_argument("--dry-run", action="store_true", help="print the sharp command and stop")
    args = ap.parse_args()

    if not args.photo.is_file():
        return f"not a file: {args.photo}"
    if args.photo.suffix.lower() not in IMAGE_EXTS:
        return (f"{args.photo.suffix!r} is not an image extension SHARP reads "
                f"({', '.join(sorted(IMAGE_EXTS))})")
    if args.fov_deg is not None and not 1.0 < args.fov_deg < 179.0:
        return "--fov-deg must be between 1 and 179"
    if args.focal_35mm is not None and args.focal_35mm <= 0:
        return "--focal-35mm must be positive"
    if args.focal_px is not None and args.focal_px <= 0:
        return "--focal-px must be positive"

    sharp_bin = shutil.which(args.sharp_bin)
    if not sharp_bin and not args.dry_run:
        return (f"the SHARP CLI ({args.sharp_bin!r}) is not on PATH.\n"
                "Install Apple's ml-sharp, then run this from that environment:\n"
                "  git clone https://github.com/apple/ml-sharp && cd ml-sharp\n"
                "  conda create -n sharp python=3.13 && conda activate sharp\n"
                "  pip install -r requirements.txt && pip install -e .\n"
                "Or point at it directly with --sharp-bin /path/to/sharp.")

    # What SHARP would assume, and what we want instead.
    assumed, width, height, source = effective_focal_35mm(args.photo)
    print(f"photo    {args.photo}  ({width}x{height})")
    print(f"focal    SHARP would assume {assumed:.1f}mm @35mm "
          f"= {f_px_from_35mm(assumed, width, height):.0f}px  [{source}]")

    wanted = None
    if args.fov_deg is not None:
        wanted = f_35mm_from_f_px((width / 2) / math.tan(math.radians(args.fov_deg) / 2),
                                  width, height)
    elif args.focal_35mm is not None:
        wanted = args.focal_35mm
    elif args.focal_px is not None:
        wanted = f_35mm_from_f_px(args.focal_px, width, height)

    stage: tempfile.TemporaryDirectory | None = None
    photo = args.photo
    if wanted is not None:
        fov = 2 * math.degrees(math.atan((width / 2) / f_px_from_35mm(wanted, width, height)))
        print(f"override using {wanted:.1f}mm @35mm "
              f"= {f_px_from_35mm(wanted, width, height):.0f}px  (hfov {fov:.1f} deg)")
        stage = tempfile.TemporaryDirectory(prefix="sharp_in_")
        photo = stage_with_focal(args.photo, wanted, Path(stage.name))
    else:
        print("         (pass --fov-deg / --focal-35mm / --focal-px to override; "
              "a wrong value warps the pothole's depth and size)")

    args.out.mkdir(parents=True, exist_ok=True)
    cmd = [sharp_bin or args.sharp_bin, "predict", "-i", str(photo), "-o", str(args.out)]
    if args.device != "default":
        cmd += ["--device", args.device]
    if args.checkpoint:
        cmd += ["-c", str(args.checkpoint)]
    if args.render:
        cmd.append("--render")

    print("running  " + " ".join(cmd), flush=True)
    if args.dry_run:
        return 0

    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        return f"sharp predict failed (exit {e.returncode})"
    finally:
        if stage:
            stage.cleanup()

    # SHARP names the output after the image stem; our staged copy keeps that stem.
    ply = args.out / f"{photo.stem}.ply"
    if not ply.is_file():
        found = sorted(args.out.glob("*.ply"))
        if not found:
            return f"sharp predict wrote no .ply into {args.out}"
        ply = found[-1]

    count = ply_gaussian_count(ply)
    gaussians = f"{count:,} gaussians, " if count else ""
    print(f"\n-> {ply}  ({gaussians}{ply.stat().st_size / 1e6:.1f} MB)")

    # The viewer resolves ?file= against the server root, so only suggest the URL
    # when the .ply actually sits under this folder.
    try:
        rel = ply.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        rel = None
    print(f"   view it:  python -m http.server 8000      (from {Path(__file__).parent})")
    if rel:
        print(f"             open http://localhost:8000/viewer/sharp.html?file={rel}")
    else:
        print(f"             then point viewer/sharp.html?file=... at {ply}\n"
              f"             (easiest: rerun with -o out, inside this folder)")
    return 0


if __name__ == "__main__":
    result = main()
    if isinstance(result, str):
        sys.exit(f"error: {result}")
    sys.exit(result)
