import Point from "@arcgis/core/geometry/Point.js";
import type Polygon from "@arcgis/core/geometry/Polygon.js";
import * as containsOperator from "@arcgis/core/geometry/operators/containsOperator.js";
import type { Hazard } from "./hazards";

export type BBox = [number, number, number, number];

export type MapTarget =
  | { center: [number, number]; zoom: number }
  | { bbox: BBox };

export interface UsState {
  code: string;
  name: string;
  bbox: BBox;
}

// Approximate state bounding boxes [west, south, east, north].
const STATE_BOUNDS: [code: string, name: string, bbox: BBox][] = [
  ["AL", "Alabama", [-88.47, 30.22, -84.89, 35.01]],
  ["AK", "Alaska", [-170.0, 51.2, -129.98, 71.39]],
  ["AZ", "Arizona", [-114.82, 31.33, -109.05, 37.0]],
  ["AR", "Arkansas", [-94.62, 33.0, -89.64, 36.5]],
  ["CA", "California", [-124.41, 32.53, -114.13, 42.01]],
  ["CO", "Colorado", [-109.06, 36.99, -102.04, 41.0]],
  ["CT", "Connecticut", [-73.73, 40.98, -71.79, 42.05]],
  ["DE", "Delaware", [-75.79, 38.45, -75.05, 39.84]],
  ["DC", "District of Columbia", [-77.12, 38.79, -76.91, 38.99]],
  ["FL", "Florida", [-87.63, 24.52, -80.03, 31.0]],
  ["GA", "Georgia", [-85.61, 30.36, -80.84, 35.0]],
  ["HI", "Hawaii", [-160.25, 18.91, -154.81, 22.24]],
  ["ID", "Idaho", [-117.24, 41.99, -111.04, 49.0]],
  ["IL", "Illinois", [-91.51, 36.97, -87.5, 42.51]],
  ["IN", "Indiana", [-88.1, 37.77, -84.78, 41.76]],
  ["IA", "Iowa", [-96.64, 40.38, -90.14, 43.5]],
  ["KS", "Kansas", [-102.05, 36.99, -94.59, 40.0]],
  ["KY", "Kentucky", [-89.57, 36.5, -81.96, 39.15]],
  ["LA", "Louisiana", [-94.04, 28.93, -88.82, 33.02]],
  ["ME", "Maine", [-71.08, 43.06, -66.95, 47.46]],
  ["MD", "Maryland", [-79.49, 37.91, -75.05, 39.72]],
  ["MA", "Massachusetts", [-73.51, 41.24, -69.93, 42.89]],
  ["MI", "Michigan", [-90.42, 41.7, -82.41, 48.31]],
  ["MN", "Minnesota", [-97.24, 43.5, -89.49, 49.38]],
  ["MS", "Mississippi", [-91.66, 30.17, -88.1, 35.0]],
  ["MO", "Missouri", [-95.77, 35.99, -89.1, 40.61]],
  ["MT", "Montana", [-116.05, 44.36, -104.04, 49.0]],
  ["NE", "Nebraska", [-104.05, 40.0, -95.31, 43.0]],
  ["NV", "Nevada", [-120.0, 35.0, -114.04, 42.0]],
  ["NH", "New Hampshire", [-72.56, 42.7, -70.61, 45.31]],
  ["NJ", "New Jersey", [-75.56, 38.93, -73.89, 41.36]],
  ["NM", "New Mexico", [-109.05, 31.33, -103.0, 37.0]],
  ["NY", "New York", [-79.76, 40.5, -71.86, 45.02]],
  ["NC", "North Carolina", [-84.32, 33.84, -75.46, 36.59]],
  ["ND", "North Dakota", [-104.05, 45.94, -96.55, 49.0]],
  ["OH", "Ohio", [-84.82, 38.4, -80.52, 41.98]],
  ["OK", "Oklahoma", [-103.0, 33.62, -94.43, 37.0]],
  ["OR", "Oregon", [-124.57, 41.99, -116.46, 46.29]],
  ["PA", "Pennsylvania", [-80.52, 39.72, -74.69, 42.27]],
  ["RI", "Rhode Island", [-71.86, 41.15, -71.12, 42.02]],
  ["SC", "South Carolina", [-83.35, 32.03, -78.54, 35.22]],
  ["SD", "South Dakota", [-104.06, 42.48, -96.44, 45.95]],
  ["TN", "Tennessee", [-90.31, 34.98, -81.65, 36.68]],
  ["TX", "Texas", [-106.65, 25.84, -93.51, 36.5]],
  ["UT", "Utah", [-114.05, 37.0, -109.04, 42.0]],
  ["VT", "Vermont", [-73.44, 42.73, -71.46, 45.02]],
  ["VA", "Virginia", [-83.68, 36.54, -75.24, 39.47]],
  ["WA", "Washington", [-124.85, 45.54, -116.92, 49.0]],
  ["WV", "West Virginia", [-82.64, 37.2, -77.72, 40.64]],
  ["WI", "Wisconsin", [-92.89, 42.49, -86.25, 47.08]],
  ["WY", "Wyoming", [-111.06, 40.99, -104.05, 45.01]],
];

export const STATES: UsState[] = STATE_BOUNDS.map(([code, name, bbox]) => ({ code, name, bbox }));

export const USA_TARGET: MapTarget = { bbox: [-125, 24.5, -66.9, 49.4] };

export const INITIAL_VIEW: { center: [number, number]; zoom: number } = {
  center: [-98.5, 39.5],
  zoom: 4,
};

export function hazardInLocation(h: Hazard, state: UsState | null, cityBoundary: Polygon | null): boolean {
  if (cityBoundary) {
    return containsOperator.execute(
      cityBoundary,
      new Point({ longitude: h.lon, latitude: h.lat }),
    );
  }
  if (state) return h.state === state.code;
  return true;
}
