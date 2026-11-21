"""Download Google Street View 360° panoramas around a hazard, using streetlevel
(https://github.com/sk-zk/streetlevel).

    python fetch_panos.py --lat 33.975725 --lon -117.333004 --radius 80 --historical 3 --out data/hazard1

Starts at the nearest panorama, walks its neighbor links within --radius, and saves
equirectangular JPEGs (GPS in EXIF, for COLMAP georeferencing) to <out>/panos/.
--historical N also grabs up to N older captures of each location (streetlevel's
`pano.historical`), which adds views from other lanes/directions.
"""

import argparse
import json
import math
from pathlib import Path

from PIL import Image
from streetlevel import streetview

SIZE = (6400, 3200)  # -> 1600 px virtual pinhole views (90 deg FOV)


def meters(lat1, lon1, lat2, lon2):
    dy = (lat2 - lat1) * 111_320.0
    dx = (lon2 - lon1) * 111_320.0 * math.cos(math.radians(lat1))
    return math.hypot(dx, dy)


def gps_exif(lat, lon):
    def dms(v):
        v = abs(v)
        d = int(v)
        m = int((v - d) * 60)
        return (d, m, round((v - d - m / 60) * 3600, 6))

    exif = Image.Exif()
    exif.get_ifd(0x8825).update({1: "N" if lat >= 0 else "S", 2: dms(lat), 3: "E" if lon >= 0 else "W", 4: dms(lon)})
    return exif


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--radius", type=float, default=50.0, help="meters")
    ap.add_argument("--historical", type=int, default=0, help="older captures per location")
    ap.add_argument("--zoom", type=int, default=4)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    pano_dir = args.out / "panos"
    pano_dir.mkdir(parents=True, exist_ok=True)

    start = streetview.find_panorama(args.lat, args.lon)
    if start is None:
        raise SystemExit("No Street View panorama near that point.")

    def save(pano):
        path = pano_dir / f"{pano.id}.jpg"
        if not path.exists():
            for attempt in range(4):  # tile requests occasionally time out
                try:
                    image = streetview.get_panorama(pano, zoom=args.zoom)
                    break
                except Exception as err:  # noqa: BLE001
                    print(f"    retry {pano.id}: {type(err).__name__}")
            else:
                return
            image = image.convert("RGB").resize(SIZE, Image.LANCZOS)
            image.save(path, quality=92, exif=gps_exif(pano.lat, pano.lon))
        kept.append({"id": pano.id, "lat": pano.lat, "lon": pano.lon,
                     "heading_deg": math.degrees(pano.heading), "date": str(pano.date)})
        print(f"  {pano.id} {pano.date} {meters(args.lat, args.lon, pano.lat, pano.lon):5.1f} m")

    queue, seen, kept = [start.id], {start.id}, []
    while queue:
        pano = streetview.find_panorama_by_id(queue.pop(0))
        if pano is None or meters(args.lat, args.lon, pano.lat, pano.lon) > args.radius:
            continue
        save(pano)
        for old in pano.historical[:args.historical]:
            old = streetview.find_panorama_by_id(old.id)
            if old is not None and old.id not in seen:
                seen.add(old.id)
                save(old)
        for n in pano.neighbors:
            if n.id not in seen and meters(args.lat, args.lon, n.lat, n.lon) <= args.radius:
                seen.add(n.id)
                queue.append(n.id)

    (args.out / "panos.json").write_text(json.dumps(
        {"center": {"lat": args.lat, "lon": args.lon}, "radius_m": args.radius, "panos": kept}, indent=2))
    print(f"Saved {len(kept)} panoramas to {pano_dir}")


if __name__ == "__main__":
    main()
