from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import base64
import io
from pathlib import Path
from PIL import Image
from models import PotholeLocation
import math
from pyproj import CRS, Transformer
from astrapy import DataAPIClient
from dotenv import load_dotenv
import uuid
import os

app = FastAPI()

# Synthetic fixture assumption; replace with the camera's calibrated pitch.
CAMERA_PITCH_DOWN_DEG = 20.0
CAMERA_HFOV_DEG = 105.0
CAMERA_VFOV_DEG = 75.0

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

def ground_plane_spatial_projection(PotHoleData: PotholeLocation):
    x_min, y_min, x_max, y_max = PotHoleData.detection.bbox_norm

    mount_height_m = 1.27 #Assuming for a Honda Clarity Plugin Hybrid 2021

    u_norm = ((x_min + x_max) / 2 - 0.5) * 2.0
    v_norm = (y_max - 0.5) * 2.0

    alpha = math.atan(u_norm * math.tan(math.radians(CAMERA_HFOV_DEG / 2.0)))
    beta = math.atan(v_norm * math.tan(math.radians(CAMERA_VFOV_DEG / 2.0)))

    total_pitch = math.radians(CAMERA_PITCH_DOWN_DEG) + beta

    if total_pitch <= math.radians(2.0):
        return None

    d_forward = mount_height_m / math.tan(total_pitch)
    r_ground = d_forward * math.cos(alpha)

    if r_ground > 50.0:
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

    return round(hazard_lat, 7), round(hazard_lon, 6)

@app.post("/findPotholeLocation")
def find_pothole_location(PotHoleData: PotholeLocation):

    image_bytes = base64.b64decode(PotHoleData.crop_jpeg_base64)

    image = Image.open(io.BytesIO(image_bytes))
    image = image.convert("RGB")

    # image_path = Path("/tmp") / f"dashdigital-pothole-{PotHoleData.device_id}.jpg"
    # image.save(image_path, format="JPEG")
    
    hazard_location = ground_plane_spatial_projection(PotHoleData)

    result = issues_table.insert_one(
        {
            "id": str(uuid.uuid4()),
            "detected_at": PotHoleData.capture_time,
            "hazard_lat": hazard_location[0],
            "hazard_lon": hazard_location[1],
            "image_base64": PotHoleData.crop_jpeg_base64,
            "status": "open", #Fix ts with actual severity classification logic
            "severity": "medium",
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
    