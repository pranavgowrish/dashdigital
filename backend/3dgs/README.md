# esri/: pothole photo → 3D Gaussian Splat (.ply)

One photo of a pothole in, one `.ply` 3D Gaussian Splat out. The reconstruction is
done by [Apple's SHARP](https://github.com/apple/ml-sharp) (`ml-sharp`); this folder
is the wrapper around it plus a viewer.

```
run_sharp.py        photo -> sharp predict -> out/<photo>.ply
viewer/sharp.html   look at the .ply in the browser
```

## Install

SHARP is a separate project and brings its own torch/gsplat stack, so install it
first and run everything from its environment:

```bash
git clone https://github.com/apple/ml-sharp && cd ml-sharp
conda create -n sharp python=3.13 && conda activate sharp
pip install -r requirements.txt && pip install -e .
sharp --help          # check it's on PATH
```

Then, back in this folder:

```bash
pip install -r requirements.txt   # just pillow, for run_sharp.py
```

The model checkpoint (`sharp_2572gikvuh.pt`, ~CDN download) is fetched automatically on
the first run and cached in `~/.cache/torch/hub/checkpoints/`. The weights are released
under Apple's own model license — check `LICENSE_MODEL` in the ml-sharp repo before
using them for anything beyond research.

## Run

```bash
python run_sharp.py photos/pothole.jpg
```

That writes `out/pothole.ply`. On Apple Silicon it runs on the GPU via MPS
automatically; `--device cpu` or `--device cuda` forces the choice.

```bash
python run_sharp.py photos/pothole.jpg --fov-deg 70 -o out   # override the lens
python run_sharp.py photos/pothole.jpg --dry-run             # print the command only
```

### Focal length is the one setting that matters

SHARP infers metric 3D from a single image, so the field of view it assumes determines
the pothole's depth and size. It reads that from EXIF, and **falls back to 30 mm with
only a log line if the photo has no focal length** — which is what you get from
screenshots, crops, and most scraped images.

`run_sharp.py` prints what SHARP is going to assume before it runs:

```
photo    photos/pothole.jpg  (4032x3024)
focal    SHARP would assume 26.0mm @35mm = 3037px  [EXIF FocalLengthIn35mmFilm]
```

If that's wrong or defaulted, override it — the script restamps the photo's EXIF in a
temp copy (your original is never modified) and hands that to SHARP:

| flag | use when |
|---|---|
| `--fov-deg 70` | you know the camera's horizontal field of view |
| `--focal-35mm 26` | you know the 35mm-equivalent focal length (phone wide ≈ 24–28 mm) |
| `--focal-px 3037` | you have real intrinsics, e.g. from a calibration |

The EXIF rules are mirrored from ml-sharp's `sharp/utils/io.py:load_rgb`, including its
quirk of multiplying a `FocalLength` below 10 mm by 8.4 to guess a crop factor.

## View the result

```bash
python -m http.server 8000      # from this folder
# open http://localhost:8000/viewer/sharp.html?file=out/pothole.ply
```

Drag to orbit, right-drag to pan, scroll to zoom. The viewer is [Spark](https://github.com/sparkjsdev/spark)
(three.js) and loads `.ply` directly.

## Output format

- `out/<photo stem>.ply` — a standard 3DGS `.ply`, so other renderers read it too.
- Coordinates are SHARP's **OpenCV camera frame**: x right, y down, z forward, metric
  with absolute scale. The photo's viewpoint is the origin and the pothole sits a few
  meters down +z. Other 3DGS tools often assume y-up, so rotate/re-center on import.

## Known limits

- The splat looks right near the photo's viewpoint and smears at steep side angles —
  there's only one view, so everything behind the pothole's rim is inferred.
- `--render` produces an orbit mp4 but needs CUDA; it's ignored on CPU and MPS.
- Scale is only as good as the focal length. An uncalibrated guess still looks fine
  on screen while being metrically wrong, so set the lens if you care about depth.
