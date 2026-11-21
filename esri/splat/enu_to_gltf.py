"""Rotate an ENU (z-up) 3DGS .ply into glTF axes (y-up: x=east, y=up, z=-north) for 3D Tiles converters.

    python enu_to_gltf.py in_enu.ply out_gltf.ply
"""
import sys

import numpy as np
from plyfile import PlyData, PlyElement

from place_pothole import mat_to_quat, quat_mul

R = np.array([[1.0, 0, 0], [0, 0, 1.0], [0, -1.0, 0]])  # (E, N, U) -> (E, U, -N)
ply = PlyData.read(sys.argv[1])
v = ply["vertex"].data.copy()
xyz = np.stack([v["x"], v["y"], v["z"]], 1) @ R.T
v["x"], v["y"], v["z"] = xyz.T
q = np.stack([v["rot_0"], v["rot_1"], v["rot_2"], v["rot_3"]], 1)
q = quat_mul(mat_to_quat(R), q / np.linalg.norm(q, axis=1, keepdims=True))
v["rot_0"], v["rot_1"], v["rot_2"], v["rot_3"] = q.T
PlyData([PlyElement.describe(v, "vertex")], text=False).write(sys.argv[2])
print(f"rotated {len(v):,} gaussians -> {sys.argv[2]}")
