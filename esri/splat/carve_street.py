"""Cut a street .splat's road gaussians out of the pothole footprint so the hole shows.

    python carve_street.py street.splat out.splat [--radius 1.0] [--x 0 --y 0]

Splats are just layered; without this the street's own asphalt covers the pothole.
"""
import argparse

import numpy as np

DT = [("p", "<f4", 3), ("s", "<f4", 3), ("c", "u1", 4), ("r", "u1", 4)]
ap = argparse.ArgumentParser()
ap.add_argument("inp"); ap.add_argument("out")
ap.add_argument("--radius", type=float, default=1.0)
ap.add_argument("--x", type=float, default=0.0); ap.add_argument("--y", type=float, default=0.0)
a = ap.parse_args()
rec = np.fromfile(a.inp, dtype=DT)
d = np.hypot(rec["p"][:, 0] - a.x, rec["p"][:, 1] - a.y)
cut = (d < a.radius) & (np.abs(rec["p"][:, 2]) < 0.6)
rec[~cut].tofile(a.out)
print(f"carved {cut.sum():,} road gaussians within {a.radius} m -> {a.out}")
