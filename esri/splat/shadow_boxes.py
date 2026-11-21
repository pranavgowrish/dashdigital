"""Capture-car shadow boxes per rig camera (x0, y0, x1, y1 as fractions of the view).

All panoramas of one Street View drive share heading and sun angle, so the shadow sits in
the same place in each rig camera's view. Read off a contact sheet of the views.
"""

SHADOW = {  # rig camera folder -> boxes to ignore
    "pano_camera0": [(0.80, 0.70, 1.00, 1.00)],
    "pano_camera1": [(0.00, 0.37, 1.00, 1.00)],
    "pano_camera2": [(0.00, 0.38, 0.40, 1.00)],
    "pano_camera5": [(0.28, 0.66, 1.00, 1.00)],
    "pano_camera6": [(0.00, 0.74, 0.34, 1.00)],
}
