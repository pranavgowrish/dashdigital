// Hazard records, shaped like the attributes on Person 3's hosted Feature Layer.
// These are MOCK records for local testing. Swap for the real FeatureLayer URL later.

export type Severity = "High" | "Medium" | "Low";
export type HazardStatus = "open" | "dispatched" | "resolved";

export interface Hazard {
  objectId: number;
  hazard_type: "pothole" | "crack";
  severity: Severity;
  confidence: number;
  status: HazardStatus;
  report_count: number;
  device_id: string;
  state: string;
  detected_at: string;
  heading_deg: number;
  lat: number;
  lon: number;
  street: string;
  image_url: string;
}

export const MOCK_HAZARDS: Hazard[] = [
  {
    objectId: 1,
    hazard_type: "pothole",
    severity: "High",
    confidence: 0.87,
    status: "open",
    report_count: 4,
    device_id: "pi5-unit-01",
    state: "CA",
    detected_at: "2026-11-21T16:30:00Z",
    heading_deg: 88.5,
    lat: 33.9737,
    lon: -117.3281,
    street: "University Ave near UCR",
    image_url: "/mock/pothole-1.jpg",
  },
  {
    objectId: 2,
    hazard_type: "pothole",
    severity: "Medium",
    confidence: 0.78,
    status: "dispatched",
    report_count: 2,
    device_id: "pi5-unit-01",
    state: "CA",
    detected_at: "2026-11-21T15:12:00Z",
    heading_deg: 270,
    lat: 33.981,
    lon: -117.3745,
    street: "Market St & University Ave",
    image_url: "/mock/pothole-2.jpg",
  },
  {
    objectId: 3,
    hazard_type: "crack",
    severity: "Low",
    confidence: 0.71,
    status: "open",
    report_count: 1,
    device_id: "pi5-unit-01",
    state: "CA",
    detected_at: "2026-11-21T14:48:00Z",
    heading_deg: 0,
    lat: 33.9825,
    lon: -117.37,
    street: "Lemon St, Downtown",
    image_url: "/mock/crack-1.jpg",
  },
  {
    objectId: 4,
    hazard_type: "pothole",
    severity: "High",
    confidence: 0.92,
    status: "open",
    report_count: 6,
    device_id: "pi5-unit-01",
    state: "CA",
    detected_at: "2026-11-21T13:05:00Z",
    heading_deg: 225,
    lat: 33.9405,
    lon: -117.403,
    street: "Magnolia Ave, Magnolia Center",
    image_url: "/mock/pothole-3.jpg",
  },
  {
    objectId: 5,
    hazard_type: "pothole",
    severity: "Medium",
    confidence: 0.69,
    status: "resolved",
    report_count: 3,
    device_id: "pi5-unit-01",
    state: "CA",
    detected_at: "2026-11-20T18:20:00Z",
    heading_deg: 180,
    lat: 33.95,
    lon: -117.3238,
    street: "Canyon Crest Dr",
    image_url: "/mock/pothole-4.jpg",
  },

  // Upland
  {
    objectId: 6,
    hazard_type: "pothole",
    severity: "High",
    confidence: 0.84,
    status: "open",
    report_count: 3,
    device_id: "pi5-unit-01",
    state: "CA",
    detected_at: "2026-11-21T12:40:00Z",
    heading_deg: 90,
    lat: 34.1067,
    lon: -117.651,
    street: "Foothill Blvd & Euclid Ave, Upland",
    image_url: "/mock/pothole-1.jpg",
  },
  {
    objectId: 7,
    hazard_type: "crack",
    severity: "Low",
    confidence: 0.73,
    status: "open",
    report_count: 1,
    device_id: "pi5-unit-01",
    state: "CA",
    detected_at: "2026-11-21T12:22:00Z",
    heading_deg: 0,
    lat: 34.0966,
    lon: -117.6508,
    street: "Euclid Ave, Downtown Upland",
    image_url: "/mock/crack-1.jpg",
  },

  // Los Angeles
  {
    objectId: 8,
    hazard_type: "pothole",
    severity: "High",
    confidence: 0.9,
    status: "dispatched",
    report_count: 8,
    device_id: "pi5-unit-01",
    state: "CA",
    detected_at: "2026-11-21T10:15:00Z",
    heading_deg: 135,
    lat: 34.048,
    lon: -118.262,
    street: "Figueroa St, Downtown LA",
    image_url: "/mock/pothole-3.jpg",
  },
  {
    objectId: 9,
    hazard_type: "pothole",
    severity: "Medium",
    confidence: 0.76,
    status: "open",
    report_count: 2,
    device_id: "pi5-unit-01",
    state: "CA",
    detected_at: "2026-11-21T09:50:00Z",
    heading_deg: 270,
    lat: 34.0779,
    lon: -118.2606,
    street: "Sunset Blvd, Echo Park",
    image_url: "/mock/pothole-2.jpg",
  },
  {
    objectId: 10,
    hazard_type: "pothole",
    severity: "Low",
    confidence: 0.67,
    status: "resolved",
    report_count: 1,
    device_id: "pi5-unit-01",
    state: "CA",
    detected_at: "2026-11-20T21:05:00Z",
    heading_deg: 90,
    lat: 34.0617,
    lon: -118.3087,
    street: "Wilshire Blvd, Koreatown",
    image_url: "/mock/pothole-4.jpg",
  },
];

export function distanceMeters(
  lat1: number,
  lon1: number,
  lat2: number,
  lon2: number,
): number {
  const R = 6371000;
  const toRad = (d: number) => (d * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}
