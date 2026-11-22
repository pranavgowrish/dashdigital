# 3dgs/: pothole + Street View → one 3D Gaussian Splat (.ply)

Called from `backend.py`'s `/render3DGaussianSplat` route via
`run_sharp.render_gaussian_splat(car_lat, car_lon, heading_deg, image_base64)`, where
`(car_lat, car_lon)` is the car's GPS position and the image is the full dashcam frame.

```
run_sharp.py      fetch 4 Street View views, stamp focal lengths, run `sharp predict` once
merge_splats.py   align the 5 SHARP .ply files to True North and merge them
out/              merged .ply files (<car_lat>_<car_lon>.ply), gitignored
```

## Pipeline

1. Street View metadata for `(lat, lon)` gives `pano_id` and the panorama's location.
2. Four 640x640 views at heading 0/90/180/270 (`fov=95`, `pitch=-5`). Heading 0 is True North.
3. Each image is restamped with an EXIF focal length (95° for Street View; the pothole photo keeps
   its EXIF focal length, else `DASHCAM_FOV_DEG`), because SHARP otherwise assumes 30 mm.
4. `sharp predict -i <input dir> -o <output dir>` runs once over all 5 images.
5. Street View splats drop `z > 18 m` and keep 50% of the rest. Every splat then has its camera's
   downward pitch leveled (5° Street View, 20° dashcam), is turned to its compass heading, and is
   lifted to its camera height (2.5 m Street View, 1.27 m dashcam). The pothole splat is also
   shifted by the car's UTM offset from the panorama. Only the vertex element is written.

Merged frame: OpenCV axes aligned to True North (East = +x, Down = +y, North = +z), in meters,
with the origin on the ground below the Street View camera.

## Install

SHARP is Apple's [ml-sharp](https://github.com/apple/ml-sharp), checked in as a git submodule at
`ml-sharp/`. It has its own torch stack, so it gets its own venv at `3dgs/.venv` (gitignored),
separate from the backend's:

```bash
git submodule update --init                     # after cloning dashdigital
cd backend/3dgs
python3.12 -m venv .venv
cd ml-sharp && ../.venv/bin/pip install -r requirements.txt && cd ..
.venv/bin/sharp --help
```

`run_sharp.py` runs `3dgs/.venv/bin/sharp` by default; set `SHARP_BIN` in `.env` to use another one.
The 2.8 GB checkpoint downloads to `~/.cache/torch/hub/checkpoints/` on the first run, or set
`SHARP_CHECKPOINT` to a local `.pt`. The weights are under Apple's own model license
(`LICENSE_MODEL` in ml-sharp).

Memory: ml-sharp holds about 8 GB at peak while loading the model, so on an 8 GB Mac it gets
killed by macOS. Use a 16 GB+ machine.

## Test

Start the backend from `backend/` (`uvicorn backend:app`), then run `python util/backend_tester.py`.
It posts to `/render3DGaussianSplat` and saves the result to `util/render3DGaussianSplat.ply`.
