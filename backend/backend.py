from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import base64
import io
from pathlib import Path
from PIL import Image
from models import PotholeLocation, GaussianSplatRequest
import math
from pyproj import CRS, Transformer
from astrapy import DataAPIClient
from dotenv import load_dotenv
import uuid
import os
import importlib
import json

sharp = importlib.import_module("3dgs.run_sharp")  # "3dgs" isn't a valid name for a plain import

app = FastAPI()

# VIOFO A119 Mini 2: 140 deg diagonal lens, modelled as an equidistant fisheye (r = f * theta).
# A plain pinhole at 140 deg puts everything about 2x too close; this model matched the 8 ft
# "AHEAD" pavement letters and the GPS distance between frames in real drive footage.
CAMERA_DIAG_FOV_DEG = 140.0
# Mount on our test car, measured from the lane-line vanishing point on a straight, flat road:
# the camera looks 3.8 deg below level and 4.3 deg left of the car's direction of travel.
CAMERA_PITCH_DOWN_DEG = 3.8
CAMERA_YAW_LEFT_DEG = 4.3
CAMERA_HEIGHT_M = 53 * 0.0254  # lens height above the road
MAX_HAZARD_RANGE_M = 50.0
# Severity from the pothole's real width across the road (m). Length along the road isn't used:
# at this shallow camera angle a few pixels of box height spans meters of road.
SEVERITY_HIGH_WIDTH_M = 0.85
SEVERITY_MEDIUM_WIDTH_M = 0.70

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

load_dotenv()

client = DataAPIClient()
db = client.get_database(
    api_endpoint=os.getenv("ASTRA_DB_API_ENDPOINT"),
    token=os.getenv("ASTRA_DB_APPLICATION_TOKEN")
)

print(f"Connected to Astra DB: {db.list_collection_names()}")

issues_table = db.get_table("issues")

def pixel_to_ground(x_norm, y_norm, image_width, image_height):
    # Returns (forward, right) in meters from the camera along the car's axes, or None above the horizon.
    x = (x_norm - 0.5) * image_width
    y = (y_norm - 0.5) * image_height
    f = math.hypot(image_width, image_height) / 2 / math.radians(CAMERA_DIAG_FOV_DEG / 2)

    # Ray in camera axes (x right, y down, z forward).
    r = math.hypot(x, y)
    theta = r / f
    ray = (0.0, 0.0, 1.0) if r == 0 else (math.sin(theta) * x / r, math.sin(theta) * y / r, math.cos(theta))

    # Car forward, up and right in camera axes, assuming no roll.
    pitch = math.radians(CAMERA_PITCH_DOWN_DEG)
    yaw = math.radians(CAMERA_YAW_LEFT_DEG)
    forward = (math.sin(yaw) * math.cos(pitch), -math.sin(pitch), math.cos(yaw) * math.cos(pitch))
    up = (-math.sin(yaw) * math.sin(pitch), -math.cos(pitch), -math.cos(yaw) * math.sin(pitch))
    right = (forward[1] * up[2] - forward[2] * up[1],
             forward[2] * up[0] - forward[0] * up[2],
             forward[0] * up[1] - forward[1] * up[0])

    dot = lambda a, b: a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
    down = -dot(ray, up)
    if down <= math.sin(math.radians(1.0)):
        return None

    scale = CAMERA_HEIGHT_M / down
    return dot(ray, forward) * scale, dot(ray, right) * scale

def estimate_severity(PotHoleData: PotholeLocation):
    # Bigger pothole on the road = more severe; measured as real width, so distance doesn't matter.
    x_min, y_min, x_max, y_max = PotHoleData.detection.bbox_norm
    width, height = PotHoleData.detection.image_width, PotHoleData.detection.image_height

    widths = []
    for y in (y_max, y_min):
        left = pixel_to_ground(x_min, y, width, height)
        right = pixel_to_ground(x_max, y, width, height)
        if left and right:
            widths.append(abs(right[1] - left[1]))
    if not widths:
        return "medium"

    width_m = sum(widths) / len(widths)
    if width_m >= SEVERITY_HIGH_WIDTH_M:
        return "high"
    if width_m >= SEVERITY_MEDIUM_WIDTH_M:
        return "medium"
    return "low"

def ground_plane_spatial_projection(PotHoleData: PotholeLocation):
    x_min, y_min, x_max, y_max = PotHoleData.detection.bbox_norm
    width, height = PotHoleData.detection.image_width, PotHoleData.detection.image_height

    # Pothole centre on the road: midpoint of the box's near (bottom) and far (top) edges.
    near = pixel_to_ground((x_min + x_max) / 2, y_max, width, height)
    if near is None:
        return None
    far = pixel_to_ground((x_min + x_max) / 2, y_min, width, height) or near
    d_forward = (near[0] + far[0]) / 2
    d_right = (near[1] + far[1]) / 2

    alpha = math.atan2(d_right, d_forward)
    r_ground = math.hypot(d_forward, d_right)

    if r_ground > MAX_HAZARD_RANGE_M:
        return None

    utm_zone = int((PotHoleData.gps.lon + 180) / 6) + 1
    epsg_code = (32600 if PotHoleData.gps.lat >= 0 else 32700) + utm_zone
    crs_utm = CRS.from_epsg(epsg_code)
    wgs84_crs = CRS.from_epsg(4326)

    to_utm = Transformer.from_crs(wgs84_crs, crs_utm, always_xy=True)
    to_wgs84 = Transformer.from_crs(crs_utm, wgs84_crs, always_xy=True)

    easting, northing = to_utm.transform(PotHoleData.gps.lon, PotHoleData.gps.lat)

    bearing_rad = math.radians(PotHoleData.gps.heading_degree) + alpha
    hazard_easting = easting + r_ground * math.sin(bearing_rad)
    hazard_northing = northing + r_ground * math.cos(bearing_rad)

    hazard_lon, hazard_lat = to_wgs84.transform(hazard_easting, hazard_northing)

    return round(hazard_lat, 7), round(hazard_lon, 7)

@app.post("/findPotholeLocation")
def find_pothole_location(PotHoleData: PotholeLocation):

    image_bytes = base64.b64decode(PotHoleData.crop_jpeg_base64)

    image = Image.open(io.BytesIO(image_bytes))
    image = image.convert("RGB")

    # image_path = Path("/tmp") / f"dashdigital-pothole-{PotHoleData.device_id}.jpg"
    # image.save(image_path, format="JPEG")
    
    hazard_location = ground_plane_spatial_projection(PotHoleData)
    if hazard_location is None:
        return {"message": "Detection is above the horizon or too far away to place on the road; not stored."}

    result = issues_table.insert_one(
        {
            "id": str(uuid.uuid4()),
            "detected_at": PotHoleData.capture_time,
            "hazard_lat": hazard_location[0],
            "hazard_lon": hazard_location[1],
            "car_lat": PotHoleData.gps.lat,
            "car_lon": PotHoleData.gps.lon,
            "heading_deg": PotHoleData.gps.heading_degree,
            "image_base64": PotHoleData.crop_jpeg_base64,
            "status": "open",
            "severity": estimate_severity(PotHoleData),
            "hazard_type": "pothole"
        }
    )

    return {
        "message": "Pothole location calculated and stored successfully.",
    }


@app.get("/getPotholeDataFromDatabase")
def get_pothole_data_from_database():
    return {"pothole_data": list(issues_table.find())}

@app.delete("/deletePotholeDataFromDatabase/{pothole_id}")
def delete_pothole_data_from_database(pothole_id):
    if (issues_table.find_one({"id": pothole_id})) is None:
        return

    issues_table.delete_one({"id" : pothole_id})
    return {"deleted": str(pothole_id)}

# Splats rendered ahead of time, one per site; manifest.json maps each pothole id to its file.
PRE_RENDERED_DIR = Path(__file__).parent / "3dgs" / "out" / "sites"

@app.api_route("/preRenderedSplat/{pothole_id}", methods=["GET", "HEAD"])
def pre_rendered_splat(pothole_id: str):
    # Fallback for the frontend when a live render takes too long.
    manifest = PRE_RENDERED_DIR / "manifest.json"
    entries = json.loads(manifest.read_text()) if manifest.exists() else []
    for entry in entries:
        ply_path = PRE_RENDERED_DIR / entry["file"]
        if entry["id"] == pothole_id and ply_path.exists():
            return FileResponse(ply_path, media_type="application/octet-stream", filename="pothole.ply")
    raise HTTPException(status_code=404, detail="No pre-rendered splat for this pothole")

@app.post("/render3DGaussianSplat")
def render_3d_gaussian_splat(SplatData: GaussianSplatRequest):
    pothole = issues_table.find_one({"id": SplatData.id})
    if pothole is None:
        raise HTTPException(status_code=404, detail="Pothole not found")

    ply_path = sharp.render_gaussian_splat(pothole["car_lat"], pothole["car_lon"], pothole["heading_deg"], pothole["image_base64"])

    return FileResponse(ply_path, media_type="application/octet-stream", filename="pothole.ply")
