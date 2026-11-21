"""Upload a Gaussian-splat .3tz to ArcGIS Online and publish it as a hosted 3D Tiles layer.

    python publish_splat.py splat/data/pothole/pkg/pothole1.3tz "DashDigital Pothole 1 (splat)"

Writes the resulting item ids to output/esri_outputs.json under "splat_layers".
"""

import sys
import time
from pathlib import Path

from arcgis.gis import ItemProperties, ItemTypeEnum

import config


def main():
    path, title = Path(sys.argv[1]), sys.argv[2]
    gis = config.connect()
    props = ItemProperties(
        title=title,
        item_type=ItemTypeEnum.TILES_PACKAGE_3D_GAUSSIAN,
        tags=config.TAGS + ["gaussian splat"],
        snippet="Pothole reconstructed from one photo (Apple ml-sharp), placed at the hazard location.",
        file_name=path.name,
    )
    print(f"Uploading {path} ({path.stat().st_size / 1e6:.1f} MB) ...")
    pkg = gis.content.folders.get().add(props, file=str(path)).result()
    print(f"  package item {pkg.id} ({pkg.type})")

    print("Publishing ...")
    t0 = time.time()
    service = pkg.publish()
    print(f"  published {service.id} ({service.type}) in {time.time() - t0:.0f}s -> {service.url}")
    config.set_sharing(pkg)
    config.set_sharing(service)

    layers = config.load_outputs().get("splat_layers", {})
    layers[title] = {"package_item_id": pkg.id, "service_item_id": service.id, "url": service.url}
    config.save_outputs(splat_layers=layers)


if __name__ == "__main__":
    main()
