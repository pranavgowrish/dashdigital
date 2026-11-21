"""Seed demo hazards near UCR so Person 4 can build against real data before the
Pi pipeline is live. Each one gets a placeholder dashcam crop attached.

Usage:
    python seed_demo.py           # add demo hazards (exercises dedupe on a repeat report)
    python seed_demo.py --clear   # delete ALL features in the layer first
"""

import argparse
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PIL import Image, ImageDraw

from hazard_client import HazardLayer

# Points snapped to real streets around UCR with Esri reverse geocoding.
DEMO = [
    # lat,       lon,         class,             severity, conf, heading, status
    (33.975725, -117.333004, "pothole",          "High",   0.91, 268.0, "open"),
    (33.975554, -117.337993, "alligator_crack",  "Medium", 0.78, 270.0, "open"),
    (33.975547, -117.340563, "pothole",          "Medium", 0.83, 90.0,  "dispatched"),
    (33.979287, -117.336515, "debris",           "High",   0.88, 92.0,  "open"),
    (33.983056, -117.336527, "longitudinal_crack", "Low",  0.71, 271.0, "open"),
    (33.981555, -117.330005, "pothole",          "Low",    0.69, 180.0, "resolved"),
    (33.981282, -117.339945, "faded_marking",    "Low",    0.74, 0.0,   "open"),
    (33.979261, -117.327981, "pothole",          "High",   0.93, 88.5,  "open"),
]

COLORS = {"High": (220, 38, 38), "Medium": (245, 158, 11), "Low": (234, 208, 30)}


def fake_crop(path, hazard_type, severity):
    img = Image.new("RGB", (320, 200), (78, 78, 82))
    draw = ImageDraw.Draw(img)
    for y in range(0, 200, 6):  # asphalt-ish noise lines
        draw.line([(0, y), (320, y + 3)], fill=(70 + y % 17, 70 + y % 13, 74), width=1)
    draw.ellipse([90, 70, 230, 150], fill=(35, 33, 32), outline=COLORS[severity], width=4)
    draw.rectangle([0, 0, 320, 26], fill=(20, 20, 20))
    draw.text((8, 7), f"DEMO {hazard_type} / {severity}", fill=(255, 255, 255))
    img.save(path, "JPEG", quality=75)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--clear", action="store_true", help="delete every feature in the layer first")
    args = parser.parse_args()

    hazards = HazardLayer()
    if args.clear:
        print(f"Deleting {hazards.count()} existing features ...")
        hazards.layer.delete_features(where="1=1")

    now = datetime.now(timezone.utc)
    with tempfile.TemporaryDirectory() as tmp:
        for i, (lat, lon, cls, sev, conf, heading, status) in enumerate(DEMO):
            jpeg = Path(tmp) / f"crop_{i}.jpg"
            fake_crop(jpeg, cls, sev)
            oid, created = hazards.upsert(
                lat, lon,
                hazard_type=cls, severity=sev, confidence=conf,
                device_id="pi5-unit-01", detected_at=now - timedelta(hours=len(DEMO) - i),
                heading_deg=heading, bbox_area=0.0143, jpeg_path=str(jpeg),
            )
            if status != "open":
                hazards.set_status(oid, status, notes="Seeded demo status")
            print(f"  {'added ' if created else 'bumped'} OBJECTID {oid}: {cls} ({sev}, {status})")

        # A second drive past the first pothole, ~1 m away: should bump report_count, not add a pin.
        lat, lon, cls, sev, *_ = DEMO[0]
        jpeg = Path(tmp) / "repeat.jpg"
        fake_crop(jpeg, cls, sev)
        oid, created = hazards.upsert(lat + 0.000009, lon, hazard_type=cls, severity=sev, confidence=0.94,
                                      device_id="pi5-unit-01", detected_at=now, jpeg_path=str(jpeg))
        print(f"  repeat report -> {'NEW PIN (dedupe failed!)' if created else f'bumped OBJECTID {oid}'}")

    print(f"Layer now has {hazards.count()} hazards.")


if __name__ == "__main__":
    main()
