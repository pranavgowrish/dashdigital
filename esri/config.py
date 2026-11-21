"""Shared settings, auth and the outputs file that Person 2 and Person 4 read."""

import json
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
OUTPUTS_PATH = ROOT / "output" / "esri_outputs.json"
SYMBOLOGY_PATH = ROOT / "output" / "symbology.json"

load_dotenv(ROOT / ".env")

ARCGIS_URL = os.getenv("ARCGIS_URL", "https://ucr.maps.arcgis.com").rstrip("/")
SERVICE_NAME = os.getenv("HAZARD_SERVICE_NAME", "dashdigital_road_hazards")
WEBSCENE_TITLE = os.getenv("WEBSCENE_TITLE", "DashDigital Road Hazard Twin")
SHARING_LEVEL = os.getenv("SHARING_LEVEL", "EVERYONE").upper()  # PRIVATE | ORGANIZATION | EVERYONE
TAGS = ["dashdigital", "road hazards", "digital twin", "cutiehack"]

# Demo area: the streets just north-west of UCR where seed_demo.py puts its hazards.
CENTER_LAT = 33.9785
CENTER_LON = -117.3345


def connect():
    """Sign in to ArcGIS Online with whichever auth method is set in .env."""
    from arcgis.gis import GIS

    username = os.getenv("ARCGIS_USERNAME")
    password = os.getenv("ARCGIS_PASSWORD")
    client_id = (os.getenv("ARCGIS_CLIENT_ID") or "").strip()
    api_key = os.getenv("ARCGIS_API_KEY")

    if username and password:
        gis = GIS(ARCGIS_URL, username, password)
    elif client_id:
        from login import cached_access_token

        token = cached_access_token()
        if not token:
            raise SystemExit("Not signed in. Run `python login.py` and follow the link.")
        gis = GIS(ARCGIS_URL, token=token)
    elif api_key:
        gis = GIS(ARCGIS_URL, api_key=api_key)
    else:
        raise SystemExit(
            "No ArcGIS credentials. Copy esri/.env.example to esri/.env and set "
            "ARCGIS_USERNAME/ARCGIS_PASSWORD, ARCGIS_CLIENT_ID (UCR SSO) or ARCGIS_API_KEY."
        )
    user = gis.users.me
    print(f"Signed in to {gis.properties.get('name', ARCGIS_URL)} as {user.username if user else '(api key)'}")
    return gis


def load_outputs():
    if OUTPUTS_PATH.exists():
        return json.loads(OUTPUTS_PATH.read_text())
    return {}


def save_outputs(**updates):
    data = load_outputs()
    data.update(updates)
    OUTPUTS_PATH.parent.mkdir(exist_ok=True)
    OUTPUTS_PATH.write_text(json.dumps(data, indent=2) + "\n")
    return data


def set_sharing(item, level=SHARING_LEVEL):
    item.sharing.sharing_level = level
    print(f"  shared {item.title!r} as {level}")
