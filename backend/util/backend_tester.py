import base64
import io
import json
from pathlib import Path
from urllib import request

from PIL import Image, ImageDraw


URL = "http://127.0.0.1:8000/findPotholeLocation"


def convert_image_to_base64_string(image_path):
    with open(image_path, "rb") as image_file:
        image_bytes = image_file.read()
        image = Image.open(io.BytesIO(image_bytes))
        image = image.convert("RGB")

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


IMAGE_PATH = Path(__file__).with_name("annotatedPothole.webp")


FAKE_POTHOLE_DATA = {
    "device_id": "test-device-001",
    "capture_time": "2026-11-21T09:02:40.533-08:00",
    "gps": {
        "lat": 37.7749,
        "lon": -122.4194,
        "heading_degree": 245.5,
        "speed_mps": 12.3,
    },
    "detection": {
        "detection_class": "pothole",
        "confidence": 0.94,
        "bbox_norm": [0.32, 0.45, 0.58, 0.72],
        "image_width": 1920,
        "image_height": 1080,
    },
    "crop_jpeg_base64": convert_image_to_base64_string(IMAGE_PATH),
}


def call_find_pothole_location():
    body = json.dumps(FAKE_POTHOLE_DATA).encode("utf-8")
    http_request = request.Request(
        URL,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with request.urlopen(http_request) as response:
        return json.loads(response.read().decode("utf-8"))


if __name__ == "__main__":
    print(json.dumps(call_find_pothole_location(), indent=2))