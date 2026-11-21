"""Hazard layer schema plus 2D/3D symbology and popup, as ArcGIS web map/scene JSON.

The JSON here is what the ArcGIS JS SDK's fromJSON() helpers accept, so Person 4
can reuse it directly (see output/symbology.json).
"""

# --- Schema (Task 3.1) -------------------------------------------------------

SEVERITIES = ["High", "Medium", "Low"]
STATUSES = ["open", "dispatched", "resolved"]


def _string(name, alias, length, domain_values=None, default=None):
    field = {
        "name": name,
        "type": "esriFieldTypeString",
        "alias": alias,
        "length": length,
        "nullable": True,
        "editable": True,
    }
    if domain_values:
        field["domain"] = {
            "type": "codedValue",
            "name": f"{name}_domain",
            "codedValues": [{"name": v, "code": v} for v in domain_values],
        }
    if default is not None:
        field["defaultValue"] = default
    return field


def _typed(name, alias, esri_type, default=None):
    field = {"name": name, "type": esri_type, "alias": alias, "nullable": True, "editable": True}
    if default is not None:
        field["defaultValue"] = default
    return field


FIELDS = [
    {"name": "OBJECTID", "type": "esriFieldTypeOID", "alias": "OBJECTID", "nullable": False, "editable": False},
    {"name": "GlobalID", "type": "esriFieldTypeGlobalID", "alias": "GlobalID", "length": 38, "nullable": False, "editable": False},
    _string("hazard_type", "Hazard type", 32),  # YOLO class name, e.g. "pothole"
    _string("severity", "Severity", 16, SEVERITIES, "Low"),
    _typed("confidence", "Detection confidence", "esriFieldTypeDouble"),
    _string("status", "Repair status", 16, STATUSES, "open"),
    _typed("report_count", "Report count", "esriFieldTypeInteger", 1),
    _string("device_id", "Device ID", 64),
    _typed("detected_at", "First detected", "esriFieldTypeDate"),
    _typed("last_reported_at", "Last reported", "esriFieldTypeDate"),
    _typed("resolved_at", "Resolved at", "esriFieldTypeDate"),
    _typed("heading_deg", "Vehicle heading (deg)", "esriFieldTypeDouble"),  # camera heading for the 3D fly-to
    _typed("bbox_area", "BBox area (normalized)", "esriFieldTypeDouble"),
    _string("notes", "Crew notes", 512),
]

# --- Symbology (Task 3.3) ----------------------------------------------------

# Display class is computed from status first, then severity:
# resolved -> green, dispatched -> blue, otherwise Red/Amber/Yellow by severity.
CLASS_EXPRESSION = """
var s = Lower(DefaultValue($feature.status, "open"));
if (s == "resolved") { return "Resolved"; }
if (s == "dispatched") { return "Dispatched"; }
return DefaultValue($feature.severity, "Low");
""".strip()

CLASSES = [
    # value,       label,                    RGB
    ("High", "Critical (high severity)", [220, 38, 38]),
    ("Medium", "Moderate (medium severity)", [245, 158, 11]),
    ("Low", "Minor (low severity)", [234, 208, 30]),
    ("Dispatched", "Crew dispatched", [37, 99, 235]),
    ("Resolved", "Repaired", [22, 163, 74]),
]

# Pins get bigger as more drives report the same hazard.
SIZE_BY_REPORTS = {
    "type": "sizeInfo",
    "field": "report_count",
    "minDataValue": 1,
    "maxDataValue": 10,
    "minSize": 10,
    "maxSize": 22,
}


def _marker_2d(rgb):
    return {
        "type": "esriSMS",
        "style": "esriSMSCircle",
        "color": rgb + [255],
        "size": 11,
        "outline": {"type": "esriSLS", "style": "esriSLSSolid", "color": [255, 255, 255, 255], "width": 1.5},
    }


def _pin_3d(rgb):
    # Icon lifted above the road with a callout line down to the exact hazard spot,
    # so pins stay readable among 3D buildings while still marking the ground point.
    return {
        "type": "PointSymbol3D",
        "symbolLayers": [
            {
                "type": "Icon",
                "resource": {"primitive": "circle"},
                "material": {"color": rgb + [1]},
                "size": 14,
                "outline": {"color": [255, 255, 255, 1], "size": 1.5},
            }
        ],
        "verticalOffset": {"screenLength": 36, "maxWorldLength": 60, "minWorldLength": 4},
        "callout": {"type": "line", "size": 1.5, "color": [255, 255, 255, 1], "border": {"color": [40, 40, 40, 0.6]}},
    }


def renderer(dimension="2d"):
    symbol = _marker_2d if dimension == "2d" else _pin_3d
    return {
        "type": "uniqueValue",
        "valueExpression": CLASS_EXPRESSION,
        "valueExpressionTitle": "Hazard status",
        "uniqueValueInfos": [
            {"value": value, "label": label, "symbol": symbol(rgb)} for value, label, rgb in CLASSES
        ],
        "defaultSymbol": symbol([120, 120, 120]),
        "defaultLabel": "Other",
        "visualVariables": [SIZE_BY_REPORTS],
    }


# --- Popup (Task 3.3) --------------------------------------------------------

POPUP = {
    "title": "{hazard_type} · {severity} severity",
    "expressionInfos": [
        {
            "name": "status_badge",
            "title": "Status badge",
            "returnType": "string",
            "expression": (
                'var s = Lower(DefaultValue($feature.status, "open"));'
                'Decode(s, "resolved", "#16a34a", "dispatched", "#2563eb", "#dc2626")'
            ),
        }
    ],
    "popupElements": [
        {"type": "attachments", "displayType": "preview", "title": "Dashcam capture"},
        {
            "type": "text",
            "text": (
                "<p><span style='background-color:{expression/status_badge};color:#fff;"
                "padding:2px 8px;border-radius:10px;font-weight:600;text-transform:uppercase;'>"
                "{status}</span></p>"
                "<p><b>{report_count}</b> report(s) &middot; confidence {confidence}</p>"
                "<p>First seen {detected_at} by {device_id}<br>Last seen {last_reported_at}</p>"
                "<p>{notes}</p>"
            ),
        },
        {"type": "fields"},
    ],
    "fieldInfos": [
        {"fieldName": "hazard_type", "label": "Hazard type", "visible": True},
        {"fieldName": "severity", "label": "Severity", "visible": True},
        {"fieldName": "status", "label": "Repair status", "visible": True},
        {"fieldName": "report_count", "label": "Report count", "visible": True, "format": {"places": 0, "digitSeparator": True}},
        {"fieldName": "confidence", "label": "Detection confidence", "visible": True, "format": {"places": 2}},
        {"fieldName": "device_id", "label": "Device ID", "visible": True},
        {"fieldName": "detected_at", "label": "First detected", "visible": True, "format": {"dateFormat": "shortDateShortTime"}},
        {"fieldName": "last_reported_at", "label": "Last reported", "visible": True, "format": {"dateFormat": "shortDateShortTime"}},
        {"fieldName": "resolved_at", "label": "Resolved at", "visible": True, "format": {"dateFormat": "shortDateShortTime"}},
        {"fieldName": "heading_deg", "label": "Vehicle heading", "visible": False, "format": {"places": 1}},
        {"fieldName": "bbox_area", "label": "BBox area", "visible": False, "format": {"places": 3}},
        {"fieldName": "notes", "label": "Crew notes", "visible": True},
    ],
    "showAttachments": True,
}
