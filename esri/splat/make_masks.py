"""Per-camera masks for the Street View car's shadow (and mast) in the panorama rig views.

    python make_masks.py <colmap model dir> <out dir>

All panoramas in one drive share heading and sun angle, so the car's shadow lands in the
same place in each rig camera's view. Masks are 255 = train on this pixel, 0 = ignore.
Regions (x0, y0, x1, y1 as fractions of the view) were read off a contact sheet of the views.
"""

import sys
from pathlib import Path

import numpy as np
import pycolmap
from PIL import Image

from shadow_boxes import SHADOW  # noqa: E402

rec = pycolmap.Reconstruction(sys.argv[1])
out = Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
folder_to_cam = {im.name.split("/")[0]: im.camera_id for im in rec.images.values()}
for folder, boxes in SHADOW.items():
    cam = rec.cameras[folder_to_cam[folder]]
    mask = np.full((cam.height, cam.width), 255, np.uint8)
    for x0, y0, x1, y1 in boxes:
        mask[int(y0 * cam.height):int(y1 * cam.height), int(x0 * cam.width):int(x1 * cam.width)] = 0
    Image.fromarray(mask).save(out / f"{cam.camera_id}.png")
    print(f"{folder} -> camera {cam.camera_id}: ignoring {100 * (mask == 0).mean():.0f}% of pixels")
