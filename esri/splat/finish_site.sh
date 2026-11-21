#!/bin/bash
# After training: street .ply -> .splat, re-place the pothole into it, point the viewer at it.
# Usage: ./finish_site.sh <trained street .ply> <site name> [pothole sharp .ply] [u v heading]
set -e
cd "$(dirname "$0")"
PLY=$1; SITE=$2
SHARP=${3:-data/pothole/sharp/kyiv_cc0.ply}; U=${4:-540}; V=${5:-330}; HEADING=${6:-268}
PY=.venv/bin/python

$PY ply2splat.py "$PLY" "viewer/splats/$SITE.splat"
$PY place_pothole.py "$SHARP" --pixel "$U" "$V" --heading "$HEADING" --enu 0 0 --radius 1.6 \
    --street "viewer/splats/$SITE.splat" --out "viewer/splats/pothole_$SITE.ply"
$PY ply2splat.py "viewer/splats/pothole_$SITE.ply" "viewer/splats/pothole_$SITE.splat" --max-dist 10
rm "viewer/splats/pothole_$SITE.ply"
$PY - "$SITE" <<'EOF'
import json, sys
site = sys.argv[1]
twins = json.load(open("viewer/twins.json"))
twins["1"] = {**twins.get("1", {}), "site": site, "pothole": f"pothole_{site}.splat"}
json.dump(twins, open("viewer/twins.json", "w"), indent=2)
print("viewer: hazard 1 ->", twins["1"])
EOF
