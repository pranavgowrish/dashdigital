"""Tasks 3.2 + 3.3: assemble the 3D Web Scene (terrain + 3D buildings + hazard layer)
with symbology and popups, publish it, and export symbology for Person 4.

Run setup_layer.py first. Re-running updates the same Web Scene in place.
"""

import json
import math
from datetime import datetime, timezone

from arcgis.gis import ItemProperties, ItemTypeEnum

import config
import symbology

OSM_BUILDINGS_ITEM = "ca0470dbbddb4db28bad74ed39949e25"
OSM_BUILDINGS_URL = "https://basemaps3d.arcgis.com/arcgis/rest/services/OpenStreetMap3D_Buildings_v1/SceneServer/layers/0"
TERRAIN_URL = "https://elevation3d.arcgis.com/arcgis/rest/services/WorldElevation3D/Terrain3D/ImageServer"
IMAGERY_URL = "https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer"
ROADS_URL = "https://services.arcgisonline.com/ArcGIS/rest/services/Reference/World_Transportation/MapServer"


def initial_camera(lat=config.CENTER_LAT, lon=config.CENTER_LON, altitude=450.0, tilt=65.0, heading=0.0):
    """Oblique camera looking north at the demo area from the south."""
    back_m = altitude * math.tan(math.radians(tilt))
    return {
        "position": {
            "x": lon,
            "y": lat - back_m / 111_320.0,
            "z": altitude,
            "spatialReference": {"wkid": 4326},
        },
        "heading": heading,
        "tilt": tilt,
    }


def buildings_renderer():
    # Muted massing so the colored hazard pins carry the visual weight.
    return {
        "type": "simple",
        "symbol": {
            "type": "MeshSymbol3D",
            "symbolLayers": [
                {
                    "type": "Fill",
                    "material": {"color": [236, 234, 228, 1], "colorMixMode": "replace"},
                    "edges": {"type": "solid", "color": [90, 90, 90, 0.35], "size": 0.6},
                }
            ],
        },
    }


def webscene_json(layer_item_id, layer_url):
    lighting_time = int(datetime(2026, 11, 21, 21, 0, tzinfo=timezone.utc).timestamp() * 1000)  # 1pm PST
    return {
        "version": "1.33",
        "authoringApp": "dashdigital",
        "authoringAppVersion": "1.0",
        "viewingMode": "global",
        "spatialReference": {"wkid": 102100, "latestWkid": 3857},
        "heightModelInfo": {"heightModel": "gravity_related_height", "vertCRS": "EGM96_Geoid", "heightUnit": "meter"},
        "baseMap": {
            "id": "dashdigital-basemap",
            "title": "Imagery with roads",
            "baseMapLayers": [
                {"id": "imagery", "title": "World Imagery", "layerType": "ArcGISTiledMapServiceLayer", "url": IMAGERY_URL, "visibility": True},
                {"id": "roads", "title": "World Transportation", "layerType": "ArcGISTiledMapServiceLayer", "url": ROADS_URL, "visibility": True, "isReference": True},
            ],
        },
        "ground": {
            "layers": [
                {"id": "terrain", "title": "Terrain3D", "layerType": "ArcGISTiledElevationServiceLayer", "url": TERRAIN_URL, "visibility": True, "listMode": "hide"}
            ],
            "transparency": 0,
            "navigationConstraint": {"type": "stayAbove"},
        },
        "operationalLayers": [
            {
                "id": "osm-buildings",
                "title": "3D Buildings (OpenStreetMap)",
                "layerType": "ArcGISSceneServiceLayer",
                "itemId": OSM_BUILDINGS_ITEM,
                "url": OSM_BUILDINGS_URL,
                "visibility": True,
                "opacity": 1,
                "disablePopup": True,
                "layerDefinition": {"drawingInfo": {"renderer": buildings_renderer()}},
            },
            {
                "id": "road-hazards",
                "title": "Road Hazards",
                "layerType": "ArcGISFeatureLayer",
                "itemId": layer_item_id,
                "url": layer_url,
                "visibility": True,
                "opacity": 1,
                # Pins sit directly on the 3D terrain surface (Task 3.2).
                "elevationInfo": {"mode": "onTheGround"},
                "screenSizePerspective": True,
                "layerDefinition": {"drawingInfo": {"renderer": symbology.renderer("3d")}},
                "popupInfo": symbology.POPUP,
                "disablePopup": False,
            },
        ],
        "initialState": {
            "environment": {
                "lighting": {"type": "sun", "datetime": lighting_time, "directShadowsEnabled": True, "displayUTCOffset": -8},
                "atmosphereEnabled": True,
                "weather": {"type": "sunny", "cloudCover": 0.3},
            },
            "viewpoint": {"camera": initial_camera()},
        },
    }


def publish(gis, data):
    outputs = config.load_outputs()
    existing = gis.content.get(outputs["webscene_item_id"]) if outputs.get("webscene_item_id") else None
    text = json.dumps(data)
    extent = [
        [config.CENTER_LON - 0.03, config.CENTER_LAT - 0.03],
        [config.CENTER_LON + 0.03, config.CENTER_LAT + 0.03],
    ]
    if existing:
        print(f"Updating Web Scene {existing.title} ({existing.id}) ...")
        existing.update(item_properties={"text": text, "extent": extent})
        return existing

    print(f"Creating Web Scene {config.WEBSCENE_TITLE!r} ...")
    props = ItemProperties(
        title=config.WEBSCENE_TITLE,
        item_type=ItemTypeEnum.WEB_SCENE,
        tags=config.TAGS,
        snippet="3D digital twin of road hazards over Riverside terrain and 3D buildings.",
        description="Terrain3D elevation + OpenStreetMap 3D Buildings + live DashDigital hazard layer.",
        type_keywords=["ViewingMode-Global"],
        extent=extent,
        text=text,
    )
    return gis.content.folders.get().add(props).result()


def export_symbology():
    """Everything Person 4 needs to render the layer the same way in the JS SDK."""
    payload = {
        "note": "ArcGIS web map/scene JSON. JS SDK: rendererJsonUtils.fromJSON(renderer2d), PopupTemplate.fromJSON(popupTemplate).",
        "renderer2d": symbology.renderer("2d"),
        "renderer3d": symbology.renderer("3d"),
        "elevationInfo3d": {"mode": "on-the-ground"},
        "popupTemplate": symbology.POPUP,
        "classes": [{"value": v, "label": label, "rgb": rgb} for v, label, rgb in symbology.CLASSES],
        "statuses": symbology.STATUSES,
        "severities": symbology.SEVERITIES,
        "headingField": "heading_deg",
    }
    config.SYMBOLOGY_PATH.parent.mkdir(exist_ok=True)
    config.SYMBOLOGY_PATH.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"Wrote {config.SYMBOLOGY_PATH.relative_to(config.ROOT)}")


def main():
    outputs = config.load_outputs()
    if "feature_layer_item_id" not in outputs:
        raise SystemExit("Run setup_layer.py first (no feature layer in output/esri_outputs.json).")

    gis = config.connect()
    data = webscene_json(outputs["feature_layer_item_id"], outputs["feature_layer_url"])
    scene = publish(gis, data)
    config.set_sharing(scene)
    export_symbology()

    result = config.save_outputs(
        webscene_item_id=scene.id,
        webscene_viewer_url=f"{config.ARCGIS_URL}/home/webscene/viewer.html?webscene={scene.id}",
        initial_camera=initial_camera(),
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
