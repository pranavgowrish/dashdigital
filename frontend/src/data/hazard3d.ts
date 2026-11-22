import type { Hazard } from "./hazards";

/**
 * Hands a hazard off to the 3D scene page (scene.html), which drapes the dashcam
 * photo onto the road surface of an ArcGIS 3D scene. Replaces the Gaussian-splat
 * viewer (sharp.html): no backend render step, so nothing to wait on but the scene.
 */
export interface Hazard3DPayload {
  id: string;
  ticket: string;
  hazard_type: string;
  severity: string;
  status: string;
  lat: number;
  lon: number;
  detected_at: string;
  /** Photo source: an http(s) URL or a data: URL. */
  image: string;
  /** Compass bearing of the dashcam, degrees clockwise from north. */
  heading_deg: number | null;
  car_lat: number | null;
  car_lon: number | null;
  stored_at: number;
}

const KEY_PREFIX = "dash3d:";
const MAX_STORED = 6;
/** Give the scene this long to report back before the caller stops waiting. */
const READY_TIMEOUT_MS = 25000;
/** Longest image source we're willing to put in a query string. */
const MAX_QUERY_IMAGE = 1200;

export const storageKey = (id: string) => `${KEY_PREFIX}${id}`;

function readStoredAt(key: string): number {
  try {
    const parsed = JSON.parse(localStorage.getItem(key) ?? "{}") as { stored_at?: unknown };
    return Number(parsed.stored_at) || 0;
  } catch {
    return 0;
  }
}

function prune() {
  const entries: { key: string; stored_at: number }[] = [];
  for (let i = 0; i < localStorage.length; i += 1) {
    const key = localStorage.key(i);
    if (!key?.startsWith(KEY_PREFIX)) continue;
    entries.push({ key, stored_at: readStoredAt(key) });
  }
  entries
    .sort((a, b) => a.stored_at - b.stored_at)
    .slice(0, Math.max(0, entries.length - (MAX_STORED - 1)))
    .forEach(({ key }) => localStorage.removeItem(key));
}

function stash(payload: Hazard3DPayload): boolean {
  try {
    prune();
    localStorage.setItem(storageKey(payload.id), JSON.stringify(payload));
    return true;
  } catch {
    return false;
  }
}

/** Small enough to survive a URL, for when localStorage is full or blocked. */
function queryFallback(payload: Hazard3DPayload): URLSearchParams {
  const params = new URLSearchParams({
    h: payload.id,
    lat: String(payload.lat),
    lon: String(payload.lon),
    ticket: payload.ticket,
    type: payload.hazard_type,
    sev: payload.severity,
    status: payload.status,
    time: payload.detected_at,
  });
  if (payload.heading_deg != null) params.set("heading", String(payload.heading_deg));
  if (payload.car_lat != null) params.set("carlat", String(payload.car_lat));
  if (payload.car_lon != null) params.set("carlon", String(payload.car_lon));
  if (payload.image && payload.image.length <= MAX_QUERY_IMAGE) params.set("img", payload.image);
  return params;
}

interface SceneMessage {
  type?: string;
  id?: string;
  message?: string;
}

/** Resolves once the scene has drawn, or rejects if it couldn't build one. */
function waitForScene(tab: Window, id: string): Promise<void> {
  return new Promise((resolve, reject) => {
    let settled = false;
    const cleanup = () => {
      settled = true;
      window.removeEventListener("message", onMessage);
      window.clearInterval(closedTimer);
      window.clearTimeout(timer);
    };
    const onMessage = (event: MessageEvent) => {
      if (settled || event.origin !== window.location.origin) return;
      const data = event.data as SceneMessage | null;
      if (data?.id !== id) return;
      if (data.type === "dash3d-ready") {
        cleanup();
        resolve();
      } else if (data.type === "dash3d-error") {
        cleanup();
        reject(new Error(data.message || "The 3D scene couldn't be built."));
      }
    };
    window.addEventListener("message", onMessage);
    // The tab being closed, or taking too long, just ends the wait.
    const closedTimer = window.setInterval(() => {
      if (!tab.closed || settled) return;
      cleanup();
      resolve();
    }, 500);
    const timer = window.setTimeout(() => {
      cleanup();
      resolve();
    }, READY_TIMEOUT_MS);
  });
}

export function openHazardIn3D(hazard: Hazard, ticket: string): Promise<void> {
  if (!Number.isFinite(hazard.lat) || !Number.isFinite(hazard.lon)) {
    return Promise.reject(new Error("This hazard has no coordinates to place in 3D."));
  }

  const payload: Hazard3DPayload = {
    id: hazard.id,
    ticket,
    hazard_type: hazard.hazard_type,
    severity: hazard.severity,
    status: hazard.status,
    lat: hazard.lat,
    lon: hazard.lon,
    detected_at: hazard.detected_at,
    image: hazard.image_url,
    heading_deg: hazard.heading_deg,
    car_lat: hazard.car_lat,
    car_lon: hazard.car_lon,
    stored_at: Date.now(),
  };

  stash(payload);
  const tab = window.open(
    `${import.meta.env.BASE_URL}scene.html?${queryFallback(payload)}`,
    `dash3d-${hazard.id}`,
  );
  if (!tab) {
    return Promise.reject(new Error("Pop-up blocked. Allow pop-ups for this site and try again."));
  }
  try {
    tab.focus();
  } catch {
    // some browsers refuse; the tab is open either way
  }
  return waitForScene(tab, hazard.id);
}
