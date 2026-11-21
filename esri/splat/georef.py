"""Put the COLMAP panorama model into local ENU meters (origin = hazard lat/lon, z=0 = road).

    python georef.py data/hazard1 [model index, default 0]

Street View panoramas along one road are nearly collinear, so a plain GPS similarity
fit can't pin down roll. Instead: "up" comes from gravity (panoramas are levelled, so
the mean down-axis of every virtual camera points down), heading + scale come from a
2D similarity between camera centers and their GPS positions, and z=0 is set at the
road surface (median height of points under the cameras).

Writes <site>/colmap/sparse_enu/0 and <site>/enu.json (origin + transform).
"""

import json
import math
import sys
from pathlib import Path

import numpy as np
import pycolmap

R_EARTH = 6_378_137.0


def to_en(lat, lon, lat0, lon0):
    return np.array([math.radians(lon - lon0) * R_EARTH * math.cos(math.radians(lat0)),
                     math.radians(lat - lat0) * R_EARTH])


def similarity_2d(src, dst):
    """Umeyama: dst ≈ s * R @ src + t for 2D point sets."""
    mu_s, mu_d = src.mean(0), dst.mean(0)
    a, b = src - mu_s, dst - mu_d
    u, sig, vt = np.linalg.svd(b.T @ a / len(src))
    d = np.diag([1, np.sign(np.linalg.det(u @ vt))])
    rot = u @ d @ vt
    scale = np.trace(np.diag(sig) @ d) / a.var(0).sum()
    return scale, rot, mu_d - scale * rot @ mu_s


def main():
    site = Path(sys.argv[1])
    meta = json.loads((site / "panos.json").read_text())
    lat0, lon0 = meta["center"]["lat"], meta["center"]["lon"]
    gps = {p["id"]: (p["lat"], p["lon"]) for p in meta["panos"]}
    model = sys.argv[2] if len(sys.argv) > 2 else "0"
    rec = pycolmap.Reconstruction(site / "colmap" / "sparse" / model)

    # 1) gravity: average image "down" (+y) axis in world over all virtual cameras.
    downs, centers = [], {}
    for img in rec.images.values():
        if not img.has_pose:
            continue
        rot_wc = img.cam_from_world().rotation.matrix().T  # camera -> world
        downs.append(rot_wc @ np.array([0.0, 1.0, 0.0]))
        pano_id = Path(img.name).stem
        centers.setdefault(pano_id, []).append(img.projection_center())
    up = -np.mean(downs, axis=0)
    up /= np.linalg.norm(up)

    # Rotate the model so that "up" becomes +z.
    z = np.array([0.0, 0.0, 1.0])
    v, c = np.cross(up, z), float(up @ z)
    vx = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    r_level = np.eye(3) + vx + vx @ vx / (1 + c)

    # 2) heading + scale: 2D similarity from levelled camera centers to GPS east/north.
    ids = [i for i in centers if i in gps]
    src = np.array([(r_level @ np.mean(centers[i], axis=0))[:2] for i in ids])
    dst = np.array([to_en(*gps[i], lat0, lon0) for i in ids])
    s, r2, t2 = similarity_2d(src, dst)
    resid = np.linalg.norm((s * (r2 @ src.T)).T + t2 - dst, axis=1)

    rot = np.eye(3)
    rot[:2, :2] = r2
    rot = rot @ r_level
    trans = np.array([t2[0], t2[1], 0.0])

    # 3) z=0 at the road: median z of points within 6 m (horizontally) of a camera
    #    and below it.
    cam_enu = np.array([s * rot @ np.mean(centers[i], axis=0) + trans for i in ids])
    pts = np.array([s * rot @ p.xyz + trans for p in rec.points3D.values()])
    near = np.min(np.linalg.norm(pts[:, None, :2] - cam_enu[None, :, :2], axis=2), axis=1) < 6
    below = pts[:, 2] < cam_enu[:, 2].mean() - 1.0
    road_z = float(np.median(pts[near & below, 2])) if (near & below).sum() > 20 else cam_enu[:, 2].mean() - 2.5
    trans[2] -= road_z

    sim3 = pycolmap.Sim3d(s, pycolmap.Rotation3d(rot), trans)
    rec.transform(sim3)
    out = site / "colmap" / "sparse_enu" / "0"
    out.mkdir(parents=True, exist_ok=True)
    rec.write(out)

    cam_h = cam_enu[:, 2].mean() - road_z
    info = {"origin": {"lat": lat0, "lon": lon0}, "frame": "ENU meters, z=0 at road surface",
            "scale": s, "gps_residual_m": {"mean": float(resid.mean()), "max": float(resid.max())},
            "camera_height_m": float(cam_h), "road_points_used": int((near & below).sum())}
    (site / "enu.json").write_text(json.dumps(info, indent=2))
    print(json.dumps(info, indent=2))


if __name__ == "__main__":
    main()
