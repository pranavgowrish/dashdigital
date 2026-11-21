# esri/splat: 3D street twin from Street View + embedded hazard

This folder turns Google Street View around a hazard into a 3D Gaussian splat, then drops a
splat of the hazard (from one photo) into the road at its real position. It's built
from public tools only:

| step | tool | script |
|---|---|---|
| fetch 360° panoramas (+ older captures) | [streetlevel](https://github.com/sk-zk/streetlevel) | `fetch_panos.py` |
| camera poses | [COLMAP `pycolmap.panorama`](https://github.com/colmap/colmap/blob/main/python/examples/panorama_sfm.py) | `run_sfm.py` |
| real-world meters (ENU, origin = hazard, z=0 = road) | GPS from EXIF + gravity | `georef.py` |
| train street splat | [gsplat `simple_trainer.py`](https://github.com/nerfstudio-project/gsplat/tree/main/examples) (cluster) or [Brush](https://github.com/ArthurBrussee/brush) (Mac) | `train*.sbatch` on the cluster |
| hazard splat from one photo | [apple/ml-sharp](https://github.com/apple/ml-sharp) (research-only weights) | `sharp predict` |
| place hazard on the road | plane fit + rigid transform + color match | `place_pothole.py` |
| compact export | antimatter15 `.splat` | `ply2splat.py` |
| web viewer | [Spark](https://github.com/sparkjsdev/spark) (three.js) | `viewer/` |

## Run

```bash
python3.12 -m venv .venv && .venv/bin/pip install pycolmap streetlevel plyfile tqdm opencv-python-headless pillow numpy
.venv/bin/python fetch_panos.py --lat 33.975725 --lon -117.333004 --radius 80 --historical 3 --out data/hazard1v2
.venv/bin/python run_sfm.py data/hazard1v2 spatial
.venv/bin/python georef.py data/hazard1v2
# train: gsplat on the cluster (see esri/README or train.sbatch), then ply2splat.py -> viewer/splats/<site>.splat
.venv/bin/python place_pothole.py <sharp.ply> --pixel U V --heading <car heading> --enu 0 0 \
    --street viewer/splats/<site>.splat --out viewer/splats/pothole_<site>.ply
python3 -m http.server 8090 --bind 127.0.0.1 --directory viewer
```

## Viewer

- `viewer/index.html?oid=1` opens the twin for hazard OBJECTID 1. The mapping lives in `viewer/twins.json`.
  This is the link for Person 4's drill-down.
- `viewer/index.html?site=hazard1&pothole=pothole_hazard1.splat&cam=x,y,z&look=x,y,z` sets the splats and camera directly.
- `viewer/sharp.html` shows the raw single-photo splat.
- The orbit is limited to street level near the drive path, where the reconstruction holds up.

`viewer/splats/` and `data/` are gitignored because they're large.

## Known limits

- The street splat is only sharp near where the Street View car drove. Aerial or far-off views fill with floaters.
- Asphalt has little texture, so the road surface right under the camera is the softest part.
- The ml-sharp hazard splat looks great near its photo's viewpoint and smears at steep side angles.
