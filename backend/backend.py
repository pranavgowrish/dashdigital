from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import base64
import io
import subprocess
import sys
from pathlib import Path
from PIL import Image
from models import PotholeLocation 

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def ground_plane_spatial_projection():
    # Placeholder for the actual ground plane spatial projection logic
    pass

@app.post("/findPotholeLocation", response_model=PotholeLocation)
def find_pothole_location(PotHoleData: PotholeLocation):

    image_bytes = base64.b64decode(PotHoleData.crop_jpeg_base64)

    image = Image.open(io.BytesIO(image_bytes))
    image = image.convert("RGB")

    # image_path = Path("/tmp") / f"dashdigital-pothole-{PotHoleData.device_id}.jpg"
    # image.save(image_path, format="JPEG")
    
    bottom_center = PotHoleData.detection.bbox_norm[0] + (PotHoleData.detection.bbox_norm[2] - PotHoleData.detection.bbox_norm[0]) / 2, PotHoleData.detection.bbox_norm[3]

    if sys.platform == "darwin":
        image_path = Path("/tmp") / f"dashdigital-pothole-{PotHoleData.device_id}.jpg"
        image.save(image_path, format="JPEG")
        subprocess.run(["open", str(image_path)], check=False)
    else:
        image.show(title=f"Pothole crop - {PotHoleData.device_id}")
    
    return PotHoleData