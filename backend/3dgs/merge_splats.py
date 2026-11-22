import math
import numpy as np
from plyfile import PlyData, PlyElement
from pyproj import CRS, Transformer

# Street View far field (sky, horizon) is mostly noise and bloats the merged file.
MAX_GSV_DEPTH_M = 18.0
GSV_KEEP_FRACTION = 0.5

# The dashcam splat is current and sharper than Street View, so it replaces Street View wherever
# it sees the road, out to this range from the car (farther out it's mostly noise).
MAX_DASHCAM_RANGE_M = 30.0
FOOTPRINT_CELL_M = 0.5

GSV_PITCH_DOWN_DEG = 5.0      # run_sharp requests Street View at pitch=-5
GSV_CAMERA_HEIGHT_M = 2.5      # Google Street View car camera
DASHCAM_HEIGHT_M = 53 * 0.0254  # keep in sync with CAMERA_HEIGHT_M in backend.py

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

def opaque(vertices):
    return 1 / (1 + np.exp(-vertices["opacity"])) > 0.5

def ground_offset(vertices, center_x, center_z, min_range_m, max_range_m):
    # The road is the densest height in a ring around the camera. Each splat's assumed camera
    # height is only roughly right (SHARP's depth scale varies), so measure where its road landed.
    distance = np.hypot(vertices["x"] - center_x, vertices["z"] - center_z)
    ring = opaque(vertices) & (distance >= min_range_m) & (distance <= max_range_m) & (np.abs(vertices["y"]) < 2)
    if ring.sum() < 500:
        return 0.0
    counts, edges = np.histogram(vertices["y"][ring], bins=200, range=(-2, 2))
    peak = counts.argmax()
    return float((edges[peak] + edges[peak + 1]) / 2)

def footprint_keys(x, z):
    return np.floor(x / FOOTPRINT_CELL_M).astype(np.int64) * 1_000_003 + np.floor(z / FOOTPRINT_CELL_M).astype(np.int64)

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
        vertices["y"] -= ground_offset(vertices, 0.0, 0.0, 2.0, 12.0)
        splats.append(vertices)

    # run_sharp already resampled the dashcam view to level and car-forward, so only the heading is left.
    pothole = level_and_rotate(load_vertices(pothole_ply), 0.0, heading_deg)
    d_east, d_north = local_offset_m(pano_lat, pano_lon, car_lat, car_lon)
    pothole["x"] += d_east
    pothole["y"] -= DASHCAM_HEIGHT_M
    pothole["z"] += d_north
    pothole = pothole[np.hypot(pothole["x"] - d_east, pothole["z"] - d_north) <= MAX_DASHCAM_RANGE_M]
    pothole["y"] -= ground_offset(pothole, d_east, d_north, 3.0, 15.0)

    # Cut Street View out wherever the dashcam sees road, plus one cell of margin, so the two
    # road surfaces don't overlap and hide the pothole.
    road = opaque(pothole) & (np.abs(pothole["y"]) < 0.3)
    cells = np.unique(np.concatenate([
        footprint_keys(pothole["x"][road] + dx, pothole["z"][road] + dz)
        for dx in (-FOOTPRINT_CELL_M, 0, FOOTPRINT_CELL_M) for dz in (-FOOTPRINT_CELL_M, 0, FOOTPRINT_CELL_M)
    ]))
    splats = [v[~np.isin(footprint_keys(v["x"], v["z"]), cells)] for v in splats]
    splats.append(pothole)

    PlyData([PlyElement.describe(np.concatenate(splats), "vertex")]).write(str(output_path))

    return output_path
