export type Severity = "High" | "Medium" | "Low";
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
  hazard_type: Hazard["hazard_type"];
  severity: Severity;
  status: HazardStatus;
  lat?: number;
  lon?: number;
  hazard_lat?: number;
  hazard_lon?: number;
  detected_at: string;
  image_url?: string;
  image_base64?: string;
}

function toImageSrc(item: ApiHazard): string {
  if (item.image_url) return item.image_url;
  if (!item.image_base64) return "";
  return item.image_base64.startsWith("data:")
    ? item.image_base64
    : `data:image/jpeg;base64,${item.image_base64}`;
}

export function normalizeHazards(items: ApiHazard[]): Hazard[] {
  return items.map((item, index) => ({
    id: String(item.id),
    objectId: index + 1,
    hazard_type: item.hazard_type,
    severity: item.severity,
    status: item.status,
    lat: Number(item.lat ?? item.hazard_lat),
    lon: Number(item.lon ?? item.hazard_lon),
    detected_at: item.detected_at,
    image_url: toImageSrc(item),
  }));
}

const MOCK_API_HAZARDS: ApiHazard[] = [
  { id: "mock-1", hazard_type: "pothole", severity: "High", status: "open", lat: 33.9737, lon: -117.3281, detected_at: "2026-11-21T16:30:00Z", image_url: "/mock/pothole-1.jpg" },
  { id: "mock-2", hazard_type: "pothole", severity: "Medium", status: "dispatched", lat: 33.981, lon: -117.3745, detected_at: "2026-11-21T15:12:00Z", image_url: "/mock/pothole-2.jpg" },
  { id: "mock-3", hazard_type: "crack", severity: "Low", status: "open", lat: 33.9825, lon: -117.37, detected_at: "2026-11-21T14:48:00Z", image_url: "/mock/crack-1.jpg" },
  { id: "mock-4", hazard_type: "pothole", severity: "High", status: "open", lat: 33.9405, lon: -117.403, detected_at: "2026-11-21T13:05:00Z", image_url: "/mock/pothole-3.jpg" },
  { id: "mock-5", hazard_type: "pothole", severity: "Medium", status: "resolved", lat: 33.95, lon: -117.3238, detected_at: "2026-11-20T18:20:00Z", image_url: "/mock/pothole-4.jpg" },
  { id: "mock-6", hazard_type: "pothole", severity: "High", status: "open", lat: 34.1067, lon: -117.651, detected_at: "2026-11-21T12:40:00Z", image_url: "/mock/pothole-1.jpg" },
  { id: "mock-7", hazard_type: "crack", severity: "Low", status: "open", lat: 34.0966, lon: -117.6508, detected_at: "2026-11-21T12:22:00Z", image_url: "/mock/crack-1.jpg" },
  { id: "mock-8", hazard_type: "pothole", severity: "High", status: "dispatched", lat: 34.048, lon: -118.262, detected_at: "2026-11-21T10:15:00Z", image_url: "/mock/pothole-3.jpg" },
  { id: "mock-9", hazard_type: "pothole", severity: "Medium", status: "open", lat: 34.0779, lon: -118.2606, detected_at: "2026-11-21T09:50:00Z", image_url: "/mock/pothole-2.jpg" },
  { id: "mock-10", hazard_type: "pothole", severity: "Low", status: "resolved", lat: 34.0617, lon: -118.3087, detected_at: "2026-11-20T21:05:00Z", image_url: "/mock/pothole-4.jpg" },
];

export const MOCK_HAZARDS: Hazard[] = normalizeHazards(MOCK_API_HAZARDS);
