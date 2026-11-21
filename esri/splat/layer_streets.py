"""Merge a sharp-but-holey street splat over a complete-but-blurry one.

    python layer_streets.py sharp.splat base.splat out.splat [--cell 0.5] [--min-count 40]

On a 2D grid, wherever the sharp splat has dense coverage, the base splat's gaussians
below the sharp surface (+ margin) are dropped; elsewhere (the voids) the base fills in.
"""
import argparse

import numpy as np

DT = [("p", "<f4", 3), ("s", "<f4", 3), ("c", "u1", 4), ("r", "u1", 4)]
ap = argparse.ArgumentParser()
ap.add_argument("sharp"); ap.add_argument("base"); ap.add_argument("out")
ap.add_argument("--cell", type=float, default=0.5)
ap.add_argument("--min-count", type=int, default=40)
ap.add_argument("--margin", type=float, default=0.8)
a = ap.parse_args()

sharp = np.fromfile(a.sharp, dtype=DT)
base = np.fromfile(a.base, dtype=DT)

# per cell: count and high percentile of the sharp surface
ij = np.floor(sharp["p"][:, :2] / a.cell).astype(np.int64)
key = ij[:, 0] * 1_000_003 + ij[:, 1]
order = np.argsort(key)
k_sorted, z_sorted = key[order], sharp["p"][order, 2]
uniq, start, count = np.unique(k_sorted, return_index=True, return_counts=True)
top = np.array([np.percentile(z_sorted[s:s + c], 95) for s, c in zip(start, count)])
dense = count >= a.min_count
cover_keys, cover_top = uniq[dense], top[dense]

bij = np.floor(base["p"][:, :2] / a.cell).astype(np.int64)
bkey = bij[:, 0] * 1_000_003 + bij[:, 1]
pos = np.searchsorted(cover_keys, bkey).clip(0, len(cover_keys) - 1)
covered = cover_keys[pos] == bkey
drop = covered & (base["p"][:, 2] < cover_top[pos] + a.margin)
merged = np.concatenate([sharp, base[~drop]])
merged.tofile(a.out)
print(f"{dense.sum():,} covered cells; dropped {drop.sum():,} of {len(base):,} base gaussians; "
      f"{len(merged):,} total -> {a.out}")
