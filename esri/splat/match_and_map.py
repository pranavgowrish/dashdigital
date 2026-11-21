"""Match + map an already-extracted panorama-rig COLMAP database using GPS-based pairs.

    python match_and_map.py data/hazard1v2 [--radius 20]

COLMAP 4 doesn't turn our panoramas' EXIF GPS into pose priors, so its SPATIAL
matcher finds no pairs. This writes an explicit pair list instead: virtual views of
panoramas within --radius meters of each other, at the same pitch. Matching and
incremental mapping then use the same rig settings as pycolmap.panorama.run_perspective.
"""

import argparse
import itertools
import json
import math
import sqlite3
from pathlib import Path

import pycolmap


def meters(a, b):
    dy = (a[0] - b[0]) * 111_320.0
    dx = (a[1] - b[1]) * 111_320.0 * math.cos(math.radians(a[0]))
    return math.hypot(dx, dy)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("site", type=Path)
    ap.add_argument("--radius", type=float, default=20.0)
    args = ap.parse_args()

    colmap = args.site / "colmap"
    db_path = colmap / "database.db"
    gps = {p["id"]: (p["lat"], p["lon"]) for p in json.loads((args.site / "panos.json").read_text())["panos"]}

    names = [r[0] for r in sqlite3.connect(db_path).execute("select name from images")]
    by_pano = {}
    for name in names:  # "pano_camera<k>/<pano id>.jpg"
        cam, file = name.split("/")
        by_pano.setdefault(Path(file).stem, []).append((int(cam.removeprefix("pano_camera")), name))

    # Rig cameras are ordered pitch-major: 0-3 look down 35 deg, 4-7 level, 8-11 up 35 deg.
    pairs = []
    for a, b in itertools.combinations(sorted(by_pano), 2):
        if a in gps and b in gps and meters(gps[a], gps[b]) <= args.radius:
            for (ka, na), (kb, nb) in itertools.product(by_pano[a], by_pano[b]):
                if ka // 4 == kb // 4:
                    pairs.append(f"{na} {nb}")
    pair_path = colmap / "pairs.txt"
    pair_path.write_text("\n".join(pairs) + "\n")
    print(f"{len(pairs):,} image pairs from {len(by_pano)} panoramas (<= {args.radius:.0f} m)")

    matching = pycolmap.FeatureMatchingOptions()
    matching.rig_verification = True
    matching.skip_image_pairs_in_same_frame = True
    matching.use_gpu = False
    pycolmap.match_image_pairs(db_path, matching_options=matching,
                               pairing_options=pycolmap.ImportedPairingOptions(match_list_path=str(pair_path)))

    opts = pycolmap.IncrementalPipelineOptions(
        ba_refine_sensor_from_rig=False, ba_refine_focal_length=False,
        ba_refine_principal_point=False, ba_refine_extra_params=False,
    )
    rec_path = colmap / "sparse"
    rec_path.mkdir(exist_ok=True)
    recs = pycolmap.incremental_mapping(db_path, colmap / "images", rec_path, opts)
    for idx, rec in recs.items():
        print(f"model {idx}: {rec.num_reg_frames()} panoramas, {rec.num_reg_images()} views, {rec.num_points3D():,} points")


if __name__ == "__main__":
    main()
