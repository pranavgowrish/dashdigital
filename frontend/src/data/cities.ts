// Every US city / town / census-designated place, from Esri Living Atlas
// "USA Census Populated Places" (public, no API key). About 31,600 places in total,
// at most ~1,900 per state, so one query per state fits under the 2,000-record limit.

import Polygon from "@arcgis/core/geometry/Polygon.js";

const PLACES_URL =
  "https://services.arcgis.com/P3ePLMYs2RVChkJx/arcgis/rest/services/USA_Census_Populated_Places/FeatureServer/0/query";

export interface CityOption {
  id: number; // FID in the Living Atlas layer
  name: string;
  kind: string; // "city" | "town" | "Census Designated Place"
  population: number;
}

const cityCache = new Map<string, Promise<CityOption[]>>();
const boundaryCache = new Map<number, Promise<Polygon | null>>();

async function query(params: Record<string, string>) {
  const res = await fetch(`${PLACES_URL}?${new URLSearchParams({ f: "json", ...params })}`);
  if (!res.ok) throw new Error(`Cities request failed: ${res.status}`);
  const json = await res.json();
  if (json.error) throw new Error(json.error.message ?? "Cities request failed");
  return json.features as { attributes: Record<string, unknown>; geometry?: unknown }[];
}

/** All places in a state, sorted by name. Cached per state. */
export function fetchCities(stateCode: string): Promise<CityOption[]> {
  let pending = cityCache.get(stateCode);
  if (!pending) {
    pending = query({
      where: `ST='${stateCode.replace(/[^A-Z]/g, "")}'`,
      outFields: "FID,NAME,CLASS,POPULATION",
      returnGeometry: "false",
      orderByFields: "NAME",
      resultRecordCount: "2000",
    }).then((features) =>
      features.map(({ attributes: a }) => ({
        id: a.FID as number,
        name: a.NAME as string,
        kind: a.CLASS as string,
        population: (a.POPULATION as number) ?? 0,
      })),
    );
    pending.catch(() => cityCache.delete(stateCode));
    cityCache.set(stateCode, pending);
  }
  return pending;
}

/** The boundary polygon of one place (WGS84). Cached per place. */
export function fetchCityBoundary(id: number): Promise<Polygon | null> {
  let pending = boundaryCache.get(id);
  if (!pending) {
    pending = query({
      objectIds: String(id),
      outFields: "FID",
      returnGeometry: "true",
      outSR: "4326",
      geometryPrecision: "5",
    }).then((features) => {
      const geometry = features[0]?.geometry as { rings: number[][][] } | undefined;
      return geometry
        ? new Polygon({ rings: geometry.rings, spatialReference: { wkid: 4326 } })
        : null;
    });
    pending.catch(() => boundaryCache.delete(id));
    boundaryCache.set(id, pending);
  }
  return pending;
}
