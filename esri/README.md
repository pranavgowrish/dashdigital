# esri/: Person 3, Esri 3D digital twin

These scripts use the ArcGIS API for Python against UCR's ArcGIS Online org (`ucr.maps.arcgis.com`). They build:

1. **Task 3.1**: a hosted point Feature Layer `road_hazards` with attachments turned on, the agreed schema, and WGS84 (wkid 4326) coordinates.
2. **Task 3.2**: a Web Scene with Terrain3D elevation, OpenStreetMap 3D Buildings, World Imagery and road labels, plus the hazard layer drawn **on the ground**.
3. **Task 3.3**: severity and status symbology (2D markers, 3D callout pins) and a popup that shows the dashcam crop.

Everything the other team members need is written to `output/esri_outputs.json` and `output/symbology.json`.

## Setup (Python 3.12)

```bash
cd esri
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in ONE auth method
```

**Auth.** UCR accounts sign in through NetID SSO, so the scripts use an OAuth app. Its Client ID is `FGbmh5sUo8DbqeuV`. Put that in `ARCGIS_CLIENT_ID` in `.env`, then:

```bash
python login.py --oob          # prints a sign-in link; after NetID login it shows a code
python login.py --code <code>  # run within ~1 minute; caches a 2-week login in output/.oauth.json
```

`python login.py` with no flags does the same thing, but a listener on `localhost:5173` catches the code automatically. Port 5173 must be free (stop the Vite dev server first).

## Run

```bash
python setup_layer.py      # 3.1: hosted layer (reuses it on re-run; --recreate to rebuild)
python build_scene.py      # 3.2 + 3.3: web scene + symbology export (updates in place on re-run)
python seed_demo.py        # optional: 8 demo hazards near UCR with photo attachments
python seed_demo.py --clear  # wipe the layer and reseed (clean demo dataset)
```

## Photoreal 3D preview (Google Photorealistic 3D Tiles)

```bash
python preview.py   # http://localhost:8000  (?oid=1 starts at hazard #1)
```

This loads the Web Scene and adds Google's photorealistic 3D layer (real buildings, trees, roads) through the Esri SDK's `IntegratedMesh3DTilesLayer`. It needs `GOOGLE_MAPS_API_KEY` in `.env` with the Map Tiles API enabled.

**Person 4:** copy the `// --- photoreal ---` block in `preview/index.html` into your SceneView setup. Three things to keep:
- Pass the key through `customParameters` (the SDK strips `?key=` from the URL).
- Hide the OSM buildings layer.
- Set the hazard layer's `elevationInfo` to `relative-to-scene` so pins rest on the mesh.

The Google layer is added in the browser and is *not* saved in the public Web Scene, so the key stays out of ArcGIS. Restrict the key to your demo domains in Google Cloud.

## Handoff

**Person 2 (backend).** Read `feature_layer_url` from `output/esri_outputs.json`, or use the helper:

```python
import sys; sys.path.append("esri")
from hazard_client import HazardLayer
layer = HazardLayer()
oid, created = layer.upsert(hazard_lat, hazard_lon, hazard_type="pothole", severity="High",
                            confidence=0.87, device_id="pi5-unit-01",
                            detected_at="2026-11-21T16:30:00Z", heading_deg=88.5,
                            bbox_area=0.0143, jpeg_path="/tmp/crop.jpg")
```

`upsert` does the 3 m same-class dedupe. On a repeat it bumps `report_count` and `last_reported_at` and attaches the new crop. Resolved hazards are excluded from the dedupe check, so a pothole that comes back after a repair gets a new pin.

**Person 4 (dashboard).**
- `feature_layer_url` / `feature_layer_item_id`: give these to the 2D `FeatureLayer`. The item already carries the 2D renderer and popup, so `new FeatureLayer({ portalItem: { id } })` picks them up.
- `webscene_item_id`: use `new WebScene({ portalItem: { id } })` for the 3D view.
- `heading_deg` field: use it as the `heading` in `goTo()` for the street-level fly-in.
- `output/symbology.json`: `renderer2d`, `renderer3d`, `popupTemplate` in ArcGIS JSON. Load them with `rendererJsonUtils.fromJSON` / `PopupTemplate.fromJSON`.
- Status updates: `featureLayer.applyEdits({ updateFeatures: [{ attributes: { OBJECTID, status: "resolved", resolved_at: Date.now() } }] })`.

## Schema

| field | type | notes |
|---|---|---|
| hazard_type | string(32) | YOLO class name (`pothole`, `alligator_crack`, ...) |
| severity | string | domain `High` / `Medium` / `Low` |
| confidence | double | 0 to 1 |
| status | string | domain `open` / `dispatched` / `resolved`, default `open` |
| report_count | int | default 1 |
| device_id | string(64) | |
| detected_at, last_reported_at, resolved_at | date | epoch ms (UTC) |
| heading_deg | double | vehicle heading at detection |
| bbox_area | double | normalized bbox area (used for severity) |
| notes | string(512) | crew notes |

## Colors

| status / severity | color |
|---|---|
| High (critical) | red |
| Medium (moderate) | amber |
| Low (minor) | yellow |
| dispatched | blue |
| resolved (repaired) | green |

Pins also grow with `report_count`.

**Sharing.** `SHARING_LEVEL=EVERYONE` (the default) makes the layer and scene public and editable, so the dashboard works without a login. That's fine for the demo, but anyone with the URL can edit. Set it to `ORGANIZATION` if UCR blocks public sharing, and then Person 4 has to add an OAuth login.
