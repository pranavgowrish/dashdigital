"""Fuse per-view ml-sharp splats of Street View rig views into one ENU splat.

    python fuse_sharp.py prep <manifest.json> <images root> <out dir>   # images + focal EXIF for sharp
    python fuse_sharp.py fuse <manifest.json> <sharp ply dir> <out.ply>

Each view's splat is in its camera frame (OpenCV, metric up to ml-sharp's scale guess).
Per panorama, one scale is fit so the camera sits at the measured height above the road
(plane fit in the downward views). Each splat is then rotated/translated into ENU with the
view's COLMAP pose. To avoid ghosting where views overlap, a gaussian is kept only by the
panorama nearest to it, and within that panorama only by the view whose optical axis is
closest to its direction (a Voronoi split over view directions, as in SPAG4d's SHARP 360).
"""

import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from plyfile import PlyData, PlyElement

from shadow_boxes import SHADOW
from place_pothole import fit_plane, mat_to_quat, quat_mul

FULL_FRAME_DIAG = math.hypot(36, 24)
NADIR_RADIUS = 3.0   # meters of road under each capture car that the other panorama supplies
SEAM_OVERLAP = 0.03  # cosine margin: views overlap slightly at their Voronoi boundaries


def view_file(v):
    return f"{v['rig_cam']}_{v['pano']}.jpg"


def prep(manifest, images_root, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    for v in manifest["views"]:
        im = Image.open(images_root / v["name"])
        exif = Image.Exif()
        # ml-sharp: f_px = FocalLength * diag_px / diag_35mm (values >= 10 are taken as 35mm-equivalent)
        exif.get_ifd(0x8769)[0x920A] = v["f"] * FULL_FRAME_DIAG / math.hypot(v["w"], v["h"])
        im.save(out_dir / view_file(v), quality=95, exif=exif)
    print(f"prepared {len(manifest['views'])} views in {out_dir}")


def fuse(manifest, ply_dir, out_path):
    views = manifest["views"]
    height = manifest["camera_height_m"]
    by_pano = {}
    for v in views:
        by_pano.setdefault(v["pano"], []).append(v)
    pano_center = {p: np.mean([vv["C"] for vv in vs], axis=0) for p, vs in by_pano.items()}

    # 1) per-panorama scale from the downward views' road plane
    scale = {}
    for p, vs in by_pano.items():
        hs = []
        for v in vs:
            if v["rig_cam"] < 4:
                d = PlyData.read(ply_dir / view_file(v).replace(".jpg", ".ply"))["vertex"].data
                xyz = np.stack([d["x"], d["y"], d["z"]], 1).astype(np.float64)
                n, p0, frac = fit_plane(xyz[np.linalg.norm(xyz, axis=1) < 15])
                hs.append(abs(p0 @ n))
        scale[p] = height / float(np.median(hs))
        print(f"pano {p}: sharp camera height {np.median(hs):.2f} m -> scale {scale[p]:.3f}")

    out, kept_total = [], 0
    centers = np.array(list(pano_center.values()))
    pano_ids = list(pano_center)
    for v in views:
        d = PlyData.read(ply_dir / view_file(v).replace(".jpg", ".ply"))["vertex"].data
        R = np.array(v["R_wc"]); C = np.array(v["C"]); s = scale[v["pano"]]
        xyz_c = np.stack([d["x"], d["y"], d["z"]], 1).astype(np.float64)
        xyz_w = (s * xyz_c) @ R.T + C
        # Voronoi by panorama (horizontal distance), except that a panorama never owns the
        # ground right under its own capture car (car + shadow): the other panorama fills it.
        hd = np.linalg.norm(xyz_w[:, None, :2] - centers[None, :, :2], axis=2)
        under = (hd < NADIR_RADIUS) & (xyz_w[:, None, 2] < 0.6)
        hd = np.where(under & ~under.all(axis=1, keepdims=True), np.inf, hd)
        keep = np.array(pano_ids)[np.argmin(hd, axis=1)] == v["pano"]
        # ... and by view direction within the panorama
        dirs = xyz_w - pano_center[v["pano"]]
        dirs /= np.linalg.norm(dirs, axis=1, keepdims=True) + 1e-9
        axes = np.array([np.array(o["R_wc"]) @ [0, 0, 1.0] for o in by_pano[v["pano"]]])
        own = [i for i, o in enumerate(by_pano[v["pano"]]) if o["name"] == v["name"]][0]
        dots = dirs @ axes.T
        keep &= dots[:, own] >= dots.max(axis=1) - SEAM_OVERLAP  # small overlap closes seams
        # own car + shadow: never keep this view's ground right under its own camera
        horiz = np.linalg.norm(xyz_w[:, :2] - C[:2], axis=1)
        keep &= ~((horiz < NADIR_RADIUS) & (xyz_w[:, 2] < 0.6))
        keep &= (np.linalg.norm(xyz_w - C, axis=1) < 150) & (xyz_w[:, 2] < 60)

        # capture car's shadow: drop gaussians that came from the shadow region of this
        # rig camera's view (same place in every panorama of the drive); the other panorama fills it
        boxes = SHADOW.get(f"pano_camera{v['rig_cam']}", [])
        if boxes:
            z = np.maximum(xyz_c[:, 2], 1e-6)
            u = (v["f"] * xyz_c[:, 0] / z + v["w"] / 2) / v["w"]
            vv = (v["f"] * xyz_c[:, 1] / z + v["h"] / 2) / v["h"]
            for x0, y0, x1, y1 in boxes:
                keep &= ~((u >= x0) & (u <= x1) & (vv >= y0) & (vv <= y1))

        e = d[keep].copy()
        e["x"], e["y"], e["z"] = xyz_w[keep].T
        q = np.stack([e["rot_0"], e["rot_1"], e["rot_2"], e["rot_3"]], 1)
        q = quat_mul(mat_to_quat(R), q / np.linalg.norm(q, axis=1, keepdims=True))
        e["rot_0"], e["rot_1"], e["rot_2"], e["rot_3"] = q.T
        for k in ("scale_0", "scale_1", "scale_2"):
            e[k] = e[k] + math.log(s)
        out.append(e)
        kept_total += keep.sum()
        print(f"  {v['name']}: kept {keep.sum():,} of {len(d):,}")

    merged = np.concatenate(out)
    PlyData([PlyElement.describe(merged, "vertex")], text=False).write(out_path)
    print(f"fused {kept_total:,} gaussians -> {out_path}")


if __name__ == "__main__":
    mode, manifest = sys.argv[1], json.loads(Path(sys.argv[2]).read_text())
    if mode == "prep":
        prep(manifest, Path(sys.argv[3]), Path(sys.argv[4]))
    else:
        fuse(manifest, Path(sys.argv[3]), Path(sys.argv[4]))
