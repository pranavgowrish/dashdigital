"""Thin wrapper over the hazard Feature Layer, for Person 2's backend (Task 2.3/2.4).

    from hazard_client import HazardLayer
    layer = HazardLayer()                      # signs in using esri/.env
    oid, created = layer.upsert(lat, lon, hazard_type="pothole", severity="High",
                                confidence=0.87, device_id="pi5-unit-01",
                                detected_at="2026-11-21T16:30:00Z", heading_deg=88.5,
                                bbox_area=0.014, jpeg_path="/tmp/crop.jpg")
"""

from datetime import datetime, timezone

from arcgis.features import FeatureLayer
from arcgis.geometry import Point
from arcgis.geometry.filters import intersects

import config

DEDUPE_RADIUS_M = 3.0


def to_epoch_ms(value):
    """ArcGIS date fields take epoch milliseconds. Accepts ISO-8601 strings or datetimes."""
    if value is None:
        value = datetime.now(timezone.utc)
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return int(value.timestamp() * 1000)


def _check(result, kind):
    rows = result.get(f"{kind}Results", [])
    if not rows or not rows[0].get("success"):
        raise RuntimeError(f"{kind} failed: {result}")
    return rows[0]["objectId"]


class HazardLayer:
    def __init__(self, gis=None, layer_url=None):
        self.gis = gis or config.connect()
        url = layer_url or config.load_outputs().get("feature_layer_url")
        if not url:
            raise SystemExit("No feature_layer_url. Run setup_layer.py first.")
        self.layer = FeatureLayer(url, self.gis)

    def find_nearby(self, lat, lon, hazard_type=None, radius_m=DEDUPE_RADIUS_M):
        """Existing hazards within radius_m of (lat, lon), nearest-first not guaranteed."""
        point = Point({"x": lon, "y": lat, "spatialReference": {"wkid": 4326}})
        where = "status <> 'resolved'"
        if hazard_type:
            where += " AND hazard_type = '{}'".format(hazard_type.replace("'", "''"))
        result = self.layer.query(
            where=where,
            geometry_filter=intersects(point, sr=4326),
            distance=radius_m,
            units="esriSRUnit_Meter",
            out_fields="*",
        )
        return result.features

    def add(self, lat, lon, *, hazard_type, severity, confidence, device_id, detected_at=None,
            heading_deg=None, bbox_area=None, jpeg_path=None):
        detected = to_epoch_ms(detected_at)
        feature = {
            "geometry": {"x": lon, "y": lat, "spatialReference": {"wkid": 4326}},
            "attributes": {
                "hazard_type": hazard_type,
                "severity": severity,
                "confidence": confidence,
                "status": "open",
                "report_count": 1,
                "device_id": device_id,
                "detected_at": detected,
                "last_reported_at": detected,
                "heading_deg": heading_deg,
                "bbox_area": bbox_area,
            },
        }
        oid = _check(self.layer.edit_features(adds=[feature]), "add")
        if jpeg_path:
            self.add_attachment(oid, jpeg_path)
        return oid

    def record_repeat(self, feature, *, detected_at=None, confidence=None, severity=None, jpeg_path=None):
        """Bump report_count on an existing hazard instead of adding a duplicate pin."""
        attrs = feature.attributes
        update = {
            "OBJECTID": attrs["OBJECTID"],
            "report_count": (attrs.get("report_count") or 1) + 1,
            "last_reported_at": to_epoch_ms(detected_at),
        }
        if confidence is not None and confidence > (attrs.get("confidence") or 0):
            update["confidence"] = confidence
        if severity is not None:
            update["severity"] = severity
        oid = _check(self.layer.edit_features(updates=[{"attributes": update}]), "update")
        if jpeg_path:
            self.add_attachment(oid, jpeg_path)
        return oid

    def upsert(self, lat, lon, *, hazard_type, jpeg_path=None, detected_at=None, confidence=None,
               severity=None, radius_m=DEDUPE_RADIUS_M, **fields):
        """Returns (objectId, created). Dedupe: same class within radius_m -> bump count."""
        nearby = self.find_nearby(lat, lon, hazard_type, radius_m)
        if nearby:
            oid = self.record_repeat(nearby[0], detected_at=detected_at, confidence=confidence,
                                     severity=severity, jpeg_path=jpeg_path)
            return oid, False
        oid = self.add(lat, lon, hazard_type=hazard_type, severity=severity or "Low",
                       confidence=confidence, detected_at=detected_at, jpeg_path=jpeg_path, **fields)
        return oid, True

    def add_attachment(self, oid, jpeg_path):
        if not self.layer.attachments.add(oid, jpeg_path):
            raise RuntimeError(f"attachment upload failed for OBJECTID {oid}")

    def set_status(self, oid, status, notes=None):
        update = {"OBJECTID": oid, "status": status}
        update["resolved_at"] = to_epoch_ms(None) if status == "resolved" else None
        if notes is not None:
            update["notes"] = notes
        return _check(self.layer.edit_features(updates=[{"attributes": update}]), "update")

    def count(self):
        return self.layer.query(return_count_only=True)
