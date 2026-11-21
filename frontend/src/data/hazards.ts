export type Severity = "high" | "medium" | "low";
export type HazardStatus = "open" | "dispatched" | "resolved";

export interface Hazard {
  id: string;
  objectId: number;
  hazard_type: "pothole" | "crack";
  severity: Severity;
  status: HazardStatus;
  lat: number;
  lon: number;
  detected_at: string;
  image_url: string;
}

export interface ApiHazard {
  id: string;
  hazard_type?: string;
  severity?: string;
  status?: string;
  lat?: number;
  lon?: number;
  hazard_lat?: number;
  hazard_lon?: number;
  detected_at: string | number | { timestamp_ms: number };
  image_url?: string;
  image_base64?: string;
}

function toIsoTime(value: ApiHazard["detected_at"]): string {
  const ms =
    typeof value === "object" && value !== null
      ? value.timestamp_ms
      : typeof value === "number"
        ? value
        : Date.parse(value);
  return Number.isFinite(ms) ? new Date(ms).toISOString() : new Date(0).toISOString();
}

function toImageSrc(item: ApiHazard): string {
  if (item.image_url) return item.image_url;
  if (!item.image_base64) return "";
  return item.image_base64.startsWith("data:")
    ? item.image_base64
    : `data:image/jpeg;base64,${item.image_base64}`;
}

const SEVERITIES: Severity[] = ["high", "medium", "low"];
const STATUSES: HazardStatus[] = ["open", "dispatched", "resolved"];

function toSeverity(value: unknown): Severity {
  const v = String(value ?? "").toLowerCase() as Severity;
  return SEVERITIES.includes(v) ? v : "medium";
}

function toStatus(value: unknown): HazardStatus {
  const v = String(value ?? "").toLowerCase() as HazardStatus;
  return STATUSES.includes(v) ? v : "open";
}

export function hazardList(payload: unknown): ApiHazard[] {
  if (Array.isArray(payload)) return payload;
  const wrapped = (payload as { pothole_data?: unknown } | null)?.pothole_data;
  return Array.isArray(wrapped) ? wrapped : [];
}

export function normalizeHazards(items: ApiHazard[]): Hazard[] {
  return items.map((item, index) => ({
    id: String(item.id),
    objectId: index + 1,
    hazard_type: item.hazard_type === "crack" ? "crack" : "pothole",
    severity: toSeverity(item.severity),
    status: toStatus(item.status),
    lat: Number(item.lat ?? item.hazard_lat),
    lon: Number(item.lon ?? item.hazard_lon),
    detected_at: toIsoTime(item.detected_at),
    image_url: toImageSrc(item),
  }));
}
