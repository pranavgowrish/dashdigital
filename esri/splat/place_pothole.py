"""Cut the pothole out of an ml-sharp splat and lay it into the street splat's ENU frame.

    python place_pothole.py data/pothole/sharp/kyiv_cc0.ply --pixel 540 330 \
        --heading 268 --enu 0 0 --radius 1.6 --out viewer/splats/pothole_hazard1.ply

ml-sharp splats are in the photo's camera frame (OpenCV: x right, y down, z forward,
metric). We fit the road plane, intersect the pothole pixel's ray with it, keep a disk
of --radius meters around that point (opacity fades out over the outer 35% so it blends
into the street's asphalt), then rotate road-normal -> +z and camera-forward -> the
vehicle heading, and translate the pothole center to --enu (meters in the street frame).
"""

import argparse
import math

import numpy as np
from plyfile import PlyData, PlyElement


def fit_plane(points, iters=400, tol=0.03, seed=0):
    rng = np.random.default_rng(seed)
    sample = points[rng.choice(len(points), min(len(points), 60_000), replace=False)]
    best, best_n = None, -1
    for _ in range(iters):
        a, b, c = sample[rng.choice(len(sample), 3, replace=False)]
        n = np.cross(b - a, c - a)
        if np.linalg.norm(n) < 1e-9:
            continue
        n /= np.linalg.norm(n)
        inliers = np.abs((sample - a) @ n) < tol
        if inliers.sum() > best_n:
            best, best_n = inliers, inliers.sum()
    pts = sample[best]
    centroid = pts.mean(0)
    n = np.linalg.svd(pts - centroid, full_matrices=False)[2][-1]  # least-squares refit on inliers
    if n @ (-centroid) < 0:  # normal points toward the camera, i.e. up out of the road
        n = -n
    return n, centroid, best_n / len(sample)


def quat_mul(q1, q2):
    w1, x1, y1, z1 = q1
    w2, x2, y2, z2 = q2.T
    return np.stack([w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
                     w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
                     w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
                     w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2], axis=1)


def mat_to_quat(m):
    w = math.sqrt(max(0.0, 1 + m[0, 0] + m[1, 1] + m[2, 2])) / 2
    x = math.copysign(math.sqrt(max(0.0, 1 + m[0, 0] - m[1, 1] - m[2, 2])) / 2, m[2, 1] - m[1, 2])
    y = math.copysign(math.sqrt(max(0.0, 1 - m[0, 0] + m[1, 1] - m[2, 2])) / 2, m[0, 2] - m[2, 0])
    z = math.copysign(math.sqrt(max(0.0, 1 - m[0, 0] - m[1, 1] + m[2, 2])) / 2, m[1, 0] - m[0, 1])
    return np.array([w, x, y, z])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ply")
    ap.add_argument("--pixel", type=float, nargs=2, required=True, help="pothole center (u v) in the photo")
    ap.add_argument("--heading", type=float, default=0.0, help="vehicle heading, degrees clockwise from north")
    ap.add_argument("--enu", type=float, nargs=2, default=(0.0, 0.0), help="pothole center in street ENU meters")
    ap.add_argument("--radius", type=float, default=1.5, help="meters of road kept around the pothole")
    ap.add_argument("--street", help="street .splat: match the pothole's asphalt color to the road there")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    ply = PlyData.read(args.ply)
    v = ply["vertex"].data
    xyz = np.stack([v["x"], v["y"], v["z"]], 1).astype(np.float64)
    K = np.asarray(ply["intrinsic"].data["intrinsic"], dtype=np.float64).reshape(3, 3)

    n, p0, inlier_frac = fit_plane(xyz)
    ray = np.linalg.solve(K, np.array([args.pixel[0], args.pixel[1], 1.0]))
    center = ray * ((p0 @ n) / (ray @ n))
    print(f"road plane inliers {inlier_frac:.0%}, pothole center {center.round(2)} m from camera "
          f"(range {np.linalg.norm(center):.1f} m)")

    # Basis change: road normal -> up (+z), camera forward on the road -> vehicle heading.
    fwd = np.array([0.0, 0.0, 1.0]) - n * n[2]
    fwd /= np.linalg.norm(fwd)
    src = np.stack([np.cross(fwd, n), fwd, n], 1)
    h = math.radians(args.heading)
    fwd_t = np.array([math.sin(h), math.cos(h), 0.0])
    up_t = np.array([0.0, 0.0, 1.0])
    dst = np.stack([np.cross(fwd_t, up_t), fwd_t, up_t], 1)
    rot = dst @ src.T

    local = (xyz - center) @ rot.T
    dist = np.linalg.norm(local[:, :2], axis=1)
    keep = (dist < args.radius) & (local[:, 2] < 0.35) & (local[:, 2] > -1.5)  # drop barriers/cones
    fade = np.clip((args.radius - dist) / (0.35 * args.radius), 0, 1) ** 2

    out = v[keep].copy()
    pos = local[keep] + np.array([args.enu[0], args.enu[1], 0.0])
    out["x"], out["y"], out["z"] = pos[:, 0], pos[:, 1], pos[:, 2]
    q = np.stack([out["rot_0"], out["rot_1"], out["rot_2"], out["rot_3"]], 1)
    q = quat_mul(mat_to_quat(rot), q / np.linalg.norm(q, axis=1, keepdims=True))
    out["rot_0"], out["rot_1"], out["rot_2"], out["rot_3"] = q.T
    alpha = 1 / (1 + np.exp(-out["opacity"].astype(np.float64))) * fade[keep]
    out["opacity"] = np.log(np.clip(alpha, 1e-6, 1 - 1e-6) / (1 - np.clip(alpha, 1e-6, 1 - 1e-6)))

    if args.street:
        # Per-channel gain so the pothole's rim asphalt matches the street's road color.
        C0 = 0.28209479177387814
        rec = np.fromfile(args.street, dtype=[("p", "<f4", 3), ("s", "<f4", 3), ("c", "u1", 4), ("r", "u1", 4)])
        d = np.linalg.norm(rec["p"][:, :2] - np.array(args.enu), axis=1)
        road = (d > 1.0) & (d < 4.0) & (np.abs(rec["p"][:, 2]) < 0.3) & (rec["c"][:, 3] > 128)
        target = np.median(rec["c"][road, :3].astype(np.float64) / 255, axis=0)
        dc = np.stack([out["f_dc_0"], out["f_dc_1"], out["f_dc_2"]], 1).astype(np.float64)
        rgb = 0.5 + C0 * dc
        rim = (dist[keep] > 0.6 * args.radius) & (np.abs(pos[:, 2]) < 0.1)
        gain = target / np.median(rgb[rim], axis=0)
        rgb = np.clip(rgb * gain, 0, 1)
        out["f_dc_0"], out["f_dc_1"], out["f_dc_2"] = ((rgb - 0.5) / C0).T
        print(f"color match: street road {target.round(3)}, gain {gain.round(3)} ({road.sum():,} road gaussians)")
        # snap to the street's actual road height around the hazard (it can differ from z=0)
        road_z = float(np.median(rec["p"][road, 2]))
        out["z"] = out["z"] + road_z
        print(f"snapped to street road height {road_z:+.2f} m")

    PlyData([PlyElement.describe(out, "vertex")], text=False).write(args.out)
    print(f"kept {keep.sum():,} of {len(v):,} gaussians -> {args.out}")


if __name__ == "__main__":
    main()
