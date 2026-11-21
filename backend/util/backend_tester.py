import base64
import io
import json
from pathlib import Path
from urllib import request

from PIL import Image


URL = "http://127.0.0.1:8000/findPotholeLocation"
DATABASE_URL = "http://127.0.0.1:8000/getPotholeDataFromDatabase"


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
        "bbox_norm": [
            371 / 1148,
            529 / 1150,
            921 / 1148,
            733 / 1150,
        ],
        "image_width": 1148,
        "image_height": 1150,
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


def test_database_retrieval():
    http_request = request.Request(DATABASE_URL, method="GET")

    with request.urlopen(http_request) as response:
        result = json.loads(response.read().decode("utf-8"))

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    # print(json.dumps(call_find_pothole_location(), indent=2))
    test_database_retrieval()
    print("Alr we good twin")