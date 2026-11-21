"""Camera poses for Street View panoramas with COLMAP's stock panorama pipeline
(pycolmap.panorama, same as colmap/python/examples/panorama_sfm.py).

    python run_sfm.py data/hazard1 [exhaustive|spatial]
"""

import logging
import sys
from pathlib import Path

from pycolmap.panorama import Mapper, Matcher, PanoramaReconstructionOptions, reconstruct

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
site = Path(sys.argv[1])
matcher = Matcher(sys.argv[2]) if len(sys.argv) > 2 else Matcher.EXHAUSTIVE  # spatial uses EXIF GPS
reconstruct(site / "panos", site / "colmap",
            PanoramaReconstructionOptions(matcher=matcher, mapper=Mapper.INCREMENTAL, use_gpu=False))
