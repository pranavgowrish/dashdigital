import math
import numpy as np
from plyfile import PlyData, PlyElement
from pyproj import CRS, Transformer

# Street View far field (sky, horizon) is mostly noise and bloats the merged file.
MAX_GSV_DEPTH_M = 18.0
GSV_KEEP_FRACTION = 0.5

GSV_PITCH_DOWN_DEG = 5.0      # run_sharp requests Street View at pitch=-5
GSV_CAMERA_HEIGHT_M = 2.5      # Google Street View car camera
DASHCAM_PITCH_DOWN_DEG = 20.0  # keep in sync with CAMERA_PITCH_DOWN_DEG in backend.py
DASHCAM_HEIGHT_M = 1.27        # keep in sync with mount_height_m in backend.py

def load_vertices(ply_path):
    # Only the vertex element is kept; SHARP's extra metadata elements confuse 3DGS viewers.
    return PlyData.read(str(ply_path))["vertex"].data.copy()

def axis_quaternion(axis, angle_deg):
    half_angle = math.radians(angle_deg) / 2
    return (math.cos(half_angle), *(math.sin(half_angle) * a for a in axis))

def quaternion_multiply(a, b):
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    return (
        aw * bw - ax * bx - ay * by - az * bz,
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
    )

def quaternion_to_matrix(q):
    w, x, y, z = q
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
        [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
        [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)],
    ])

def level_and_rotate(vertices, pitch_down_deg, heading_deg):
    # SHARP splats are in OpenCV camera coordinates (+x right, +y down, +z forward).
    # First undo the camera's downward pitch (a negative turn about +x), then turn it to its
    # compass heading: clockwise seen from above, which is a positive turn about +y (down).
    q = quaternion_multiply(axis_quaternion((0, 1, 0), heading_deg), axis_quaternion((1, 0, 0), -pitch_down_deg))

    positions = np.stack([vertices["x"], vertices["y"], vertices["z"]], axis=1) @ quaternion_to_matrix(q).T
    vertices["x"], vertices["y"], vertices["z"] = positions.T

    # Pre-multiply each Gaussian's (w, x, y, z) quaternion by the same rotation.
    rotations = quaternion_multiply(q, [vertices[f"rot_{i}"].copy() for i in range(4)])
    for i in range(4):
        vertices[f"rot_{i}"] = rotations[i]

    return vertices

def local_offset_m(origin_lat, origin_lon, lat, lon):
    utm_zone = int((origin_lon + 180) / 6) + 1
    epsg_code = (32600 if origin_lat >= 0 else 32700) + utm_zone
    to_utm = Transformer.from_crs(CRS.from_epsg(4326), CRS.from_epsg(epsg_code), always_xy=True)

    origin_easting, origin_northing = to_utm.transform(origin_lon, origin_lat)
    easting, northing = to_utm.transform(lon, lat)

    return easting - origin_easting, northing - origin_northing

def merge_splats(gsv_plys, pothole_ply, pano_lat, pano_lon, car_lat, car_lon, heading_deg, output_path):
    # Merged frame: OpenCV axes aligned to True North, East = +x, Down = +y, North = +z,
    # with the origin on the ground directly below the Street View camera.
    rng = np.random.default_rng(0)
    splats = []

    for view_heading, ply_path in gsv_plys.items():
        vertices = load_vertices(ply_path)
        vertices = vertices[vertices["z"] <= MAX_GSV_DEPTH_M]
        vertices = vertices[rng.random(len(vertices)) < GSV_KEEP_FRACTION]
        vertices = level_and_rotate(vertices, GSV_PITCH_DOWN_DEG, view_heading)
        vertices["y"] -= GSV_CAMERA_HEIGHT_M
        splats.append(vertices)

    pothole = level_and_rotate(load_vertices(pothole_ply), DASHCAM_PITCH_DOWN_DEG, heading_deg)
    d_east, d_north = local_offset_m(pano_lat, pano_lon, car_lat, car_lon)
    pothole["x"] += d_east
    pothole["y"] -= DASHCAM_HEIGHT_M
    pothole["z"] += d_north
    splats.append(pothole)

    PlyData([PlyElement.describe(np.concatenate(splats), "vertex")]).write(str(output_path))

    return output_path
