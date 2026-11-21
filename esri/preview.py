"""Serve the 3D twin preview (Esri Web Scene + Google Photorealistic 3D Tiles).

    python preview.py   # then open http://localhost:8000

Writes preview/config.js (gitignored) from .env and output/esri_outputs.json.
"""

import http.server
import json
import os
import socketserver

import config

PORT = 8000
PREVIEW_DIR = config.ROOT / "preview"


def write_config():
    outputs = config.load_outputs()
    if "webscene_item_id" not in outputs:
        raise SystemExit("Run build_scene.py first.")
    cfg = {
        "portalUrl": config.ARCGIS_URL,
        "webSceneId": outputs["webscene_item_id"],
        "featureLayerUrl": outputs["feature_layer_url"],
        "googleKey": (os.getenv("GOOGLE_MAPS_API_KEY") or "").strip(),
    }
    (PREVIEW_DIR / "config.js").write_text(f"window.TWIN_CONFIG = {json.dumps(cfg, indent=2)};\n")


def main():
    write_config()
    handler = lambda *a: http.server.SimpleHTTPRequestHandler(*a, directory=str(PREVIEW_DIR))  # noqa: E731
    with socketserver.TCPServer(("localhost", PORT), handler) as httpd:
        print(f"Twin preview on http://localhost:{PORT}  (add ?oid=1 to start at a hazard)")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
