"""Task 3.1: create the hosted point Feature Layer for road hazards (attachments on).

Usage:
    python setup_layer.py             # create, or reuse the layer in output/esri_outputs.json
    python setup_layer.py --recreate  # delete the existing service and build a fresh one
"""

import argparse
import json

from arcgis.features import FeatureLayerCollection

import config
import symbology

CAPABILITIES = "Create,Delete,Query,Update,Editing"


def layer_definition():
    return {
        "id": 0,
        "name": "road_hazards",
        "type": "Feature Layer",
        "geometryType": "esriGeometryPoint",
        "displayField": "hazard_type",
        "description": "Road hazards detected by DashDigital Pi 5 dashcams.",
        "objectIdField": "OBJECTID",
        "globalIdField": "GlobalID",
        "hasAttachments": True,
        "hasZ": False,
        "hasM": False,
        "capabilities": CAPABILITIES,
        "maxRecordCount": 2000,
        "allowGeometryUpdates": True,
        "supportsAttachmentsByUploadId": True,
        "extent": _extent(),
        "fields": symbology.FIELDS,
        "drawingInfo": {"renderer": symbology.renderer("2d"), "transparency": 0},
        "templates": [
            {
                "name": "Road hazard",
                "description": "",
                "drawingTool": "esriFeatureEditToolPoint",
                "prototype": {"attributes": {"status": "open", "report_count": 1, "severity": "Low"}},
            }
        ],
        "types": [],
        "indexes": [],
    }


def _extent(pad=0.05):
    return {
        "xmin": config.CENTER_LON - pad,
        "ymin": config.CENTER_LAT - pad,
        "xmax": config.CENTER_LON + pad,
        "ymax": config.CENTER_LAT + pad,
        "spatialReference": {"wkid": 4326},
    }


def find_existing(gis):
    item_id = config.load_outputs().get("feature_layer_item_id")
    if item_id:
        item = gis.content.get(item_id)
        if item:
            return item
    me = gis.users.me.username
    hits = gis.content.search(f'title:"{config.SERVICE_NAME}" AND owner:{me}', item_type="Feature Service")
    return next((i for i in hits if i.title == config.SERVICE_NAME), None)


def create(gis):
    if not gis.content.is_service_name_available(config.SERVICE_NAME, "featureService"):
        raise SystemExit(
            f"Service name {config.SERVICE_NAME!r} is taken in this org. "
            "Set HAZARD_SERVICE_NAME in .env to something unique."
        )
    print(f"Creating hosted feature service {config.SERVICE_NAME!r} ...")
    item = gis.content.create_service(
        name=config.SERVICE_NAME,
        service_description="DashDigital road hazards (edge dashcam detections)",
        capabilities=CAPABILITIES,
        wkid=4326,  # Person 2 writes raw WGS84 lon/lat, no reprojection needed
        max_record_count=2000,
        tags=config.TAGS,
        snippet="Live road hazards from Raspberry Pi 5 dashcams, with dashcam crop attachments.",
        create_params={
            "name": config.SERVICE_NAME,
            "spatialReference": {"wkid": 4326},
            "initialExtent": _extent(),
            "fullExtent": _extent(),
            "allowGeometryUpdates": True,
            "units": "esriDecimalDegrees",
            "xssPreventionInfo": {"xssPreventionEnabled": True, "xssPreventionRule": "InputOnly", "xssInputRule": "rejectInvalid"},
        },
    )
    flc = FeatureLayerCollection.fromitem(item)
    result = flc.manager.add_to_definition({"layers": [layer_definition()]})
    if not result.get("success"):
        raise SystemExit(f"add_to_definition failed: {result}")
    return item


def configure_item(item):
    """Store popup + renderer on the item so every Esri client (Map Viewer, JS SDK
    via portalItem, Scene Viewer) shows the same thing."""
    item_data = {
        "layers": [
            {
                "id": 0,
                "popupInfo": symbology.POPUP,
                "layerDefinition": {"drawingInfo": {"renderer": symbology.renderer("2d")}},
            }
        ]
    }
    item.update(item_properties={"text": json.dumps(item_data)})
    config.set_sharing(item)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--recreate", action="store_true", help="delete the existing service first")
    args = parser.parse_args()

    gis = config.connect()
    item = find_existing(gis)
    if item and args.recreate:
        print(f"Deleting existing {item.title} ({item.id}) ...")
        item.protect(False)
        item.delete(permanent=True)
        item = None

    if item:
        print(f"Reusing existing feature layer {item.title} ({item.id})")
    else:
        item = create(gis)
    configure_item(item)

    service_url = item.url
    outputs = config.save_outputs(
        portal_url=config.ARCGIS_URL,
        feature_layer_item_id=item.id,
        feature_service_url=service_url,
        feature_layer_url=f"{service_url}/0",
        sharing_level=config.SHARING_LEVEL,
    )
    print(json.dumps(outputs, indent=2))
    print(f"\nItem page: {config.ARCGIS_URL}/home/item.html?id={item.id}")


if __name__ == "__main__":
    main()
