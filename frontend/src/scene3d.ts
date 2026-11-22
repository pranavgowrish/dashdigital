import "@arcgis/core/assets/esri/themes/dark/main.css";
import Graphic from "@arcgis/core/Graphic.js";
import EsriMap from "@arcgis/core/Map.js";
import Extent from "@arcgis/core/geometry/Extent.js";
import Point from "@arcgis/core/geometry/Point.js";
import Polygon from "@arcgis/core/geometry/Polygon.js";
import * as webMercatorUtils from "@arcgis/core/geometry/support/webMercatorUtils.js";
import GraphicsLayer from "@arcgis/core/layers/GraphicsLayer.js";
import MediaLayer from "@arcgis/core/layers/MediaLayer.js";
import SceneLayer from "@arcgis/core/layers/SceneLayer.js";
import ExtentAndRotationGeoreference from "@arcgis/core/layers/support/ExtentAndRotationGeoreference.js";
import ImageElement from "@arcgis/core/layers/support/ImageElement.js";
import * as reactiveUtils from "@arcgis/core/core/reactiveUtils.js";
import SceneView from "@arcgis/core/views/SceneView.js";
import { storageKey, type Hazard3DPayload } from "./data/hazard3d";

const WEB_MERCATOR = { wkid: 3857 };
const OSM_BUILDINGS =
  "https://basemaps3d.arcgis.com/arcgis/rest/services/OpenStreetMap3D_Buildings_v1/SceneServer";
const DEFAULT_PATCH_M = 3;
const SETTLE_TIMEOUT_MS = 12000;
const SEVERITY_COLOR: Record<string, number[]> = {
  high: [220, 38, 38],
  medium: [245, 158, 11],
  low: [234, 179, 8],
};

const params = new URLSearchParams(location.search);
const el = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;

function readPayload(): Hazard3DPayload | null {
  const id = params.get("h");
  if (id) {
    try {
      const raw = localStorage.getItem(storageKey(id));
      if (raw) return JSON.parse(raw) as Hazard3DPayload;
    } catch {
      // fall through to the query string
    }
  }
  const lat = Number(params.get("lat"));
  const lon = Number(params.get("lon"));
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null;
  const num = (key: string) => {
    const n = Number(params.get(key));
    return params.get(key) != null && Number.isFinite(n) ? n : null;
  };
  return {
    id: id ?? "",
    ticket: params.get("ticket") ?? "",
    hazard_type: params.get("type") ?? "hazard",
    severity: params.get("sev") ?? "medium",
    status: params.get("status") ?? "open",
    lat,
    lon,
    detected_at: params.get("time") ?? "",
    image: params.get("img") ?? "",
    heading_deg: num("heading"),
    car_lat: num("carlat"),
    car_lon: num("carlon"),
    stored_at: Date.now(),
  };
}

function tellOpener(type: "dash3d-ready" | "dash3d-error", id: string, message?: string) {
  try {
    window.opener?.postMessage({ type, id, message }, location.origin);
  } catch {
    // the panel falls back to a timeout
  }
}

function showStatus(text: string) {
  const box = el("status");
  box.textContent = text;
  box.hidden = false;
}

const payload = readPayload();
if (!payload) {
  el<HTMLHeadingElement>("title").textContent = "No hazard to show";
  showStatus(
    'Open this page from the "View in 3D" button in the hazard panel, or pass coordinates, ' +
      "e.g. ?lat=37.7749&lon=-122.4194&heading=90.",
  );
  throw new Error("scene3d: no hazard payload");
}

const hazard = payload;
const label = hazard.hazard_type.charAt(0).toUpperCase() + hazard.hazard_type.slice(1);
document.title = `${label} in 3D${hazard.ticket ? ` · ${hazard.ticket}` : ""}`;
el<HTMLHeadingElement>("title").textContent = `${label} in 3D`;
el("ticket").textContent = hazard.ticket;
el("severity").textContent = hazard.severity;
el("status-value").textContent = hazard.status;
el("detected").textContent = hazard.detected_at
  ? new Date(hazard.detected_at).toLocaleString(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    })
  : "—";
el("coords").textContent = `${hazard.lat.toFixed(5)}, ${hazard.lon.toFixed(5)}`;
el("heading").textContent =
  hazard.heading_deg == null ? "unknown" : `${Math.round(hazard.heading_deg)}°`;

/** Web Mercator units per true ground metre at this latitude. */
const unitsPerMetre = 1 / Math.cos((hazard.lat * Math.PI) / 180);
const [centerX, centerY] = webMercatorUtils.lngLatToXY(hazard.lon, hazard.lat);
const hazardPoint = new Point({
  longitude: hazard.lon,
  latitude: hazard.lat,
  spatialReference: { wkid: 4326 },
});
/** MediaLayer rotation: clockwise angle of north from the top of the image. */
const headingRotation = ((360 - (hazard.heading_deg ?? 0)) % 360 + 360) % 360;

const map = new EsriMap({ basemap: "satellite", ground: "world-elevation" });
const view = new SceneView({
  container: "view",
  map,
  qualityProfile: "high",
  popupEnabled: false,
  environment: { atmosphereEnabled: true, starsEnabled: false },
  center: [hazard.lon, hazard.lat],
  zoom: 18,
});

const outlineLayer = new GraphicsLayer({
  title: "Hazard outline",
  elevationInfo: { mode: "on-the-ground" },
});
map.add(outlineLayer);

const buildings = new SceneLayer({ url: OSM_BUILDINGS, visible: false, opacity: 0.9 });
buildings
  .load()
  .then(() => map.add(buildings))
  .catch(() => {
    const toggle = el<HTMLInputElement>("toggle-buildings");
    toggle.disabled = true;
    toggle.parentElement?.setAttribute("title", "3D building service unavailable");
  });

/** A rectangle of the given size, centred on the hazard and turned to face the heading. */
function patchGeoreference(sizeM: number, aspect: number, rotation: number) {
  const halfW = (sizeM * unitsPerMetre) / 2;
  const halfH = halfW / aspect;
  return new ExtentAndRotationGeoreference({
    extent: new Extent({
      xmin: centerX - halfW,
      ymin: centerY - halfH,
      xmax: centerX + halfW,
      ymax: centerY + halfH,
      spatialReference: WEB_MERCATOR,
    }),
    rotation,
  });
}

/** The same rectangle as a polygon, so the patch is findable from far away. */
function patchOutline(sizeM: number, aspect: number, rotation: number) {
  const halfW = (sizeM * unitsPerMetre) / 2;
  const halfH = halfW / aspect;
  // rotation is the clockwise angle of north from the image top, so the image top
  // points along bearing -rotation.
  const bearing = (-rotation * Math.PI) / 180;
  const up = [Math.sin(bearing), Math.cos(bearing)];
  const right = [Math.cos(bearing), -Math.sin(bearing)];
  const corner = (sx: number, sy: number) => [
    centerX + sx * halfW * right[0] + sy * halfH * up[0],
    centerY + sx * halfW * right[1] + sy * halfH * up[1],
  ];
  return new Polygon({
    rings: [[corner(-1, 1), corner(1, 1), corner(1, -1), corner(-1, -1), corner(-1, 1)]],
    spatialReference: WEB_MERCATOR,
  });
}

function drawOutline(sizeM: number, aspect: number, rotation: number) {
  const color = SEVERITY_COLOR[hazard.severity] ?? SEVERITY_COLOR.medium;
  outlineLayer.removeAll();
  outlineLayer.add(
    new Graphic({
      geometry: patchOutline(sizeM, aspect, rotation),
      symbol: {
        type: "simple-fill",
        color: [0, 0, 0, 0],
        outline: { color: [...color, 0.95], width: 2 },
      },
    }),
  );
}

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    if (!src) {
      reject(new Error("This hazard has no photo to place on the road."));
      return;
    }
    const img = new Image();
    if (/^https?:/i.test(src) && !src.startsWith(location.origin)) img.crossOrigin = "anonymous";
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error("The hazard photo couldn't be loaded."));
    img.src = src;
  });
}

const CAMERAS = {
  dashcam: { tilt: 72, scale: 220 },
  top: { tilt: 0, scale: 90 },
  wide: { tilt: 45, scale: 2500 },
};

function goToView(name: keyof typeof CAMERAS) {
  const { tilt, scale } = CAMERAS[name];
  view
    .goTo(
      {
        target: hazardPoint,
        scale,
        tilt,
        heading: name === "top" ? 0 : (hazard.heading_deg ?? 0),
      },
      { animate: true, duration: 900 },
    )
    .catch(() => {});
}

/** Builds the scene. Returns a problem to report, or "" when all is well. */
async function build(): Promise<string> {
  let img: HTMLImageElement | null = null;
  let problem = "";
  try {
    img = await loadImage(hazard.image);
  } catch (err) {
    // No photo is survivable: the scene and the outline still show where the hazard is.
    problem = (err as Error).message;
  }
  const aspect = img ? img.naturalWidth / img.naturalHeight || 1.5 : 1.5;

  let sizeM = DEFAULT_PATCH_M;
  let rotation = headingRotation;

  const element = img
    ? new ImageElement({ image: img, georeference: patchGeoreference(sizeM, aspect, rotation) })
    : null;
  const photoLayer = element
    ? new MediaLayer({ title: "Hazard photo", source: [element] })
    : null;
  if (photoLayer) map.add(photoLayer);
  drawOutline(sizeM, aspect, rotation);

  const sizeInput = el<HTMLInputElement>("size");
  const rotationInput = el<HTMLInputElement>("rotation");
  const opacityInput = el<HTMLInputElement>("opacity");
  sizeInput.value = String(sizeM);
  rotationInput.value = String(Math.round(rotation));
  el("size-out").textContent = `${sizeM.toFixed(1)} m`;
  el("rotation-out").textContent = `${Math.round(rotation)}°`;

  const refresh = () => {
    if (element) element.georeference = patchGeoreference(sizeM, aspect, rotation);
    if (el<HTMLInputElement>("toggle-outline").checked) drawOutline(sizeM, aspect, rotation);
  };

  sizeInput.addEventListener("input", () => {
    sizeM = Number(sizeInput.value);
    el("size-out").textContent = `${sizeM.toFixed(1)} m`;
    refresh();
  });
  rotationInput.addEventListener("input", () => {
    rotation = Number(rotationInput.value);
    el("rotation-out").textContent = `${rotation}°`;
    refresh();
  });
  opacityInput.addEventListener("input", () => {
    const pct = Number(opacityInput.value);
    if (photoLayer) photoLayer.opacity = pct / 100;
    el("opacity-out").textContent = `${pct}%`;
  });
  el<HTMLInputElement>("toggle-outline").addEventListener("change", (event) => {
    const on = (event.target as HTMLInputElement).checked;
    if (on) drawOutline(sizeM, aspect, rotation);
    else outlineLayer.removeAll();
  });
  el<HTMLInputElement>("toggle-buildings").addEventListener("change", (event) => {
    buildings.visible = (event.target as HTMLInputElement).checked;
  });
  el("view-dashcam").addEventListener("click", () => goToView("dashcam"));
  el("view-top").addEventListener("click", () => goToView("top"));
  el("view-wide").addEventListener("click", () => goToView("wide"));

  await view.when();
  goToView("dashcam");
  el("controls").hidden = false;
  // Let the scene settle before telling the panel it can unlock, but never hold it
  // hostage to a slow tile.
  await Promise.race([
    reactiveUtils.whenOnce(() => !view.updating),
    new Promise((resolve) => setTimeout(resolve, SETTLE_TIMEOUT_MS)),
  ]);
  return problem;
}

build()
  .then((problem) => {
    if (!problem) {
      tellOpener("dash3d-ready", hazard.id);
      return;
    }
    showStatus(problem);
    tellOpener("dash3d-error", hazard.id, problem);
  })
  .catch((err: Error) => {
    showStatus(err.message || "The 3D scene couldn't be built.");
    tellOpener("dash3d-error", hazard.id, err.message);
  });
