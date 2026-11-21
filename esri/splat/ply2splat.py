"""3DGS .ply -> antimatter15 .splat (32 B/gaussian), dropping faint and far-away gaussians.
Usage: python ply2splat.py in.ply out.splat [--max-dist 150] [--min-alpha 0.02]"""
import argparse, numpy as np
ap = argparse.ArgumentParser(); ap.add_argument("inp"); ap.add_argument("out")
ap.add_argument("--max-dist", type=float, default=150.0); ap.add_argument("--min-alpha", type=float, default=0.02)
a = ap.parse_args()
with open(a.inp, "rb") as f:
    names, n = [], 0
    while (line := f.readline().decode().strip()) != "end_header":
        if line.startswith("element vertex"): n = int(line.split()[-1])
        elif line.startswith("property float"): names.append(line.split()[-1])
    d = np.frombuffer(f.read(n * 4 * len(names)), dtype=np.float32).reshape(n, len(names))
col = {k: d[:, i] for i, k in enumerate(names)}
xyz = np.stack([col["x"], col["y"], col["z"]], 1)
alpha = 1 / (1 + np.exp(-col["opacity"]))
scale = np.exp(np.stack([col["scale_0"], col["scale_1"], col["scale_2"]], 1))
keep = (alpha > a.min_alpha) & (np.linalg.norm(xyz, axis=1) < a.max_dist)
order = np.argsort(-(alpha * scale.prod(1))[keep])
idx = np.flatnonzero(keep)[order]
C0 = 0.28209479177387814
rgb = np.clip((0.5 + C0 * np.stack([col["f_dc_0"], col["f_dc_1"], col["f_dc_2"]], 1)) * 255, 0, 255)
q = np.stack([col["rot_0"], col["rot_1"], col["rot_2"], col["rot_3"]], 1)
q = q / np.linalg.norm(q, axis=1, keepdims=True)
rec = np.zeros(len(idx), dtype=[("p", "<f4", 3), ("s", "<f4", 3), ("c", "u1", 4), ("r", "u1", 4)])
rec["p"], rec["s"] = xyz[idx], scale[idx]
rec["c"] = np.concatenate([rgb[idx], (alpha[idx] * 255)[:, None]], 1).astype(np.uint8)
rec["r"] = np.clip(q[idx] * 128 + 128, 0, 255).astype(np.uint8)
rec.tofile(a.out)
print(f"{n:,} -> {len(idx):,} gaussians, {rec.nbytes/1e6:.1f} MB")
