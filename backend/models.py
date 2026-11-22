from pydantic import BaseModel

class gpsModel(BaseModel):
    lat: float
    lon: float
    heading_degree: float
    speed_mps: float

class detectionModel(BaseModel):
    detection_class: str
    confidence: float
    bbox_norm: list[float]
    image_width: int
    image_height: int

class PotholeLocation(BaseModel):
    device_id: str
    capture_time: str
    gps: gpsModel
    detection: detectionModel
    crop_jpeg_base64: str

class GaussianSplatRequest(BaseModel):
    lat: float
    lon: float
    heading_deg: float
    image_base64: str
