"""Build a training dataset with the capture car + its shadow cropped out.

    python make_v4.py data/hazard1v3 data/hazard1v4 [--min-angle -45]

The 4 downward rig cameras (pitch -35) see the Street View car and its shadow near the
bottom of every frame. Crop those views to rows looking above --min-angle (degrees below
the horizon). Cropping only the bottom keeps fx, cx, cy unchanged; only the height shrinks.
"""

import argparse
import math
import shutil
from pathlib import Path

import pycolmap
from PIL import Image

DOWN_CAMS = {"pano_camera0", "pano_camera1", "pano_camera2", "pano_camera3"}  # pitch -35
DOWN_PITCH = -35.0

ap = argparse.ArgumentParser()
ap.add_argument("src", type=Path)
ap.add_argument("dst", type=Path)
ap.add_argument("--min-angle", type=float, default=-45.0)
args = ap.parse_args()

rec = pycolmap.Reconstruction(args.src / "colmap" / "sparse_enu" / "0")
img_dir = args.dst / "train" / "images"
img_dir.mkdir(parents=True, exist_ok=True)

cropped_cams = {}
for im in rec.images.values():
    folder = im.name.split("/")[0]
    src = args.src / "colmap" / "images" / im.name
    dst = img_dir / im.name
    dst.parent.mkdir(exist_ok=True)
    if folder in DOWN_CAMS:
        cam = rec.cameras[im.camera_id]
        f, cy = cam.params[0], cam.params[2]
        keep = int(cy + f * math.tan(math.radians(DOWN_PITCH - args.min_angle)))  # rows below cy look further down
        Image.open(src).crop((0, 0, cam.width, keep)).save(dst, quality=95)
        cropped_cams[im.camera_id] = keep
    else:
        shutil.copy2(src, dst)

for cid, h in cropped_cams.items():
    rec.cameras[cid].height = h
out = args.dst / "train" / "sparse" / "0"
out.mkdir(parents=True, exist_ok=True)
rec.write(out)
shutil.copy2(args.src / "enu.json", args.dst / "enu.json")
print(f"{rec.num_reg_images()} views; cropped cameras {sorted(cropped_cams)} to height {set(cropped_cams.values())}")
