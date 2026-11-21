import Polygon from "@arcgis/core/geometry/Polygon.js";

const PLACES_URL =
  "https://services.arcgis.com/P3ePLMYs2RVChkJx/arcgis/rest/services/USA_Census_Populated_Places/FeatureServer/0/query";
const STATES_URL =
  "https://services.arcgis.com/P3ePLMYs2RVChkJx/arcgis/rest/services/USA_States_Generalized_Boundaries/FeatureServer/0/query";

export interface CityOption {
  id: number;
  name: string;
  kind: string;
  population: number;
}

const cityCache = new Map<string, Promise<CityOption[]>>();
const boundaryCache = new Map<number, Promise<Polygon | null>>();
const stateBoundaryCache = new Map<string, Promise<Polygon | null>>();

async function query(params: Record<string, string>, url = PLACES_URL) {
  const res = await fetch(`${url}?${new URLSearchParams({ f: "json", ...params })}`);
  if (!res.ok) throw new Error(`Boundary request failed: ${res.status}`);
  const json = await res.json();
  if (json.error) throw new Error(json.error.message ?? "Boundary request failed");
  return json.features as { attributes: Record<string, unknown>; geometry?: unknown }[];
}

function toPolygon(features: { geometry?: unknown }[]): Polygon | null {
  const geometry = features[0]?.geometry as { rings: number[][][] } | undefined;
  return geometry ? new Polygon({ rings: geometry.rings, spatialReference: { wkid: 4326 } }) : null;
}

export function fetchStateBoundary(stateCode: string): Promise<Polygon | null> {
  let pending = stateBoundaryCache.get(stateCode);
  if (!pending) {
    pending = query(
      {
        where: `STATE_ABBR='${stateCode.replace(/[^A-Z]/g, "")}'`,
        outFields: "STATE_ABBR",
        returnGeometry: "true",
        outSR: "4326",
        geometryPrecision: "4",
        maxAllowableOffset: "0.005",
      },
      STATES_URL,
    ).then(toPolygon);
    pending.catch(() => stateBoundaryCache.delete(stateCode));
    stateBoundaryCache.set(stateCode, pending);
  }
  return pending;
}
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

export function fetchCityBoundary(id: number): Promise<Polygon | null> {
  let pending = boundaryCache.get(id);
  if (!pending) {
    pending = query({
      objectIds: String(id),
      outFields: "FID",
      returnGeometry: "true",
      outSR: "4326",
      geometryPrecision: "5",
    }).then(toPolygon);
    pending.catch(() => boundaryCache.delete(id));
    boundaryCache.set(id, pending);
  }
  return pending;
}
