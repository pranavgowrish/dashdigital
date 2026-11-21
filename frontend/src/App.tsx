import Graphic from "@arcgis/core/Graphic.js";
import Extent from "@arcgis/core/geometry/Extent.js";
import type Polygon from "@arcgis/core/geometry/Polygon.js";
import type Viewpoint from "@arcgis/core/Viewpoint.js";
import { useRef, useState } from "react";
import { HazardMap } from "./components/HazardMap";
import { Sidebar } from "./components/Sidebar";
import { STATES, USA_TARGET, hazardInLocation, type MapTarget } from "./data/areas";
import { fetchCities, fetchCityBoundary, type CityOption } from "./data/cities";
import { MOCK_HAZARDS } from "./data/hazards";

function goToTarget(target: MapTarget) {
  if ("bbox" in target) {
    const [xmin, ymin, xmax, ymax] = target.bbox;
    return new Extent({ xmin, ymin, xmax, ymax, spatialReference: { wkid: 4326 } });
  }
  return { center: target.center, zoom: target.zoom };
}

const BOUNDARY_SYMBOL = {
  type: "simple-fill" as const,
  color: [37, 99, 235, 0.06],
  outline: { color: [37, 99, 235, 0.9], width: 2 },
};

function App() {
  const mapRef = useRef<HTMLArcgisMapElement | null>(null);
  const [stateCode, setStateCode] = useState<string | null>(null);
  const [cities, setCities] = useState<CityOption[]>([]);
  const [citiesLoading, setCitiesLoading] = useState(false);
  const [citiesError, setCitiesError] = useState<string | null>(null);
  const [city, setCity] = useState<CityOption | null>(null);
  const [cityBoundary, setCityBoundary] = useState<Polygon | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [panelOpen, setPanelOpen] = useState(true);
  const latestState = useRef<string | null>(null);
  const latestCity = useRef<number | null>(null);
  const viewBeforeHazard = useRef<Viewpoint | null>(null);

  const state = STATES.find((s) => s.code === stateCode) ?? null;
  const hazards = MOCK_HAZARDS;
  const locationHazards = hazards.filter((h) => hazardInLocation(h, state, cityBoundary));
  const selected = hazards.find((h) => h.objectId === selectedId) ?? null;

  const flyTo = (target: MapTarget | Polygon) => {
    const goal = "bbox" in target || "center" in target ? goToTarget(target as MapTarget) : target;
    mapRef.current?.goTo(goal).catch(() => {});
  };

  const drawBoundary = (boundary: Polygon | null) => {
    const graphics = mapRef.current?.graphics;
    graphics?.removeAll();
    if (boundary) graphics?.add(new Graphic({ geometry: boundary, symbol: BOUNDARY_SYMBOL }));
  };

  const changeCity = (next: CityOption | null) => {
    setCity(next);
    setCityBoundary(null);
    setSelectedId(null);
    viewBeforeHazard.current = null;
    drawBoundary(null);
    latestCity.current = next?.id ?? null;
    if (!next) {
      if (state) flyTo({ bbox: state.bbox });
      return;
    }
    fetchCityBoundary(next.id)
      .then((boundary) => {
        if (latestCity.current !== next.id || !boundary) return;
        setCityBoundary(boundary);
        drawBoundary(boundary);
        flyTo(boundary);
      })
      .catch(() => {});
  };

  const changeState = (code: string | null) => {
    setStateCode(code);
    setCity(null);
    setCityBoundary(null);
    setSelectedId(null);
    viewBeforeHazard.current = null;
    drawBoundary(null);
    latestCity.current = null;
    latestState.current = code;
    setCities([]);
    setCitiesError(null);

    const next = STATES.find((s) => s.code === code);
    flyTo(next ? { bbox: next.bbox } : USA_TARGET);
    if (!next) return;

    setCitiesLoading(true);
    fetchCities(next.code)
      .then((list) => {
        if (latestState.current === next.code) setCities(list);
      })
      .catch((err: Error) => {
        if (latestState.current === next.code) setCitiesError(err.message);
      })
      .finally(() => {
        if (latestState.current === next.code) setCitiesLoading(false);
      });
  };

  const selectHazard = (objectId: number | null) => {
    const h = hazards.find((x) => x.objectId === objectId);
    if (h && selectedId == null) {
      viewBeforeHazard.current = mapRef.current?.viewpoint?.clone() ?? null;
    }
    if (!h) viewBeforeHazard.current = null;
    setSelectedId(objectId);
    if (h) {
      setPanelOpen(true);
      flyTo({ center: [h.lon, h.lat], zoom: 17 });
    }
  };

  const exitHazard = () => {
    setSelectedId(null);
    const previous = viewBeforeHazard.current;
    viewBeforeHazard.current = null;
    if (previous) mapRef.current?.goTo(previous).catch(() => {});
    else if (cityBoundary) flyTo(cityBoundary);
    else if (state) flyTo({ bbox: state.bbox });
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-slate-100 text-slate-900">
      <main className="relative min-w-60 flex-1">
        <HazardMap
          hazards={hazards}
          selectedId={selectedId}
          onSelect={selectHazard}
          mapRef={mapRef}
        />

        {!panelOpen && (
          <button
            type="button"
            onClick={() => setPanelOpen(true)}
            aria-controls="triage-panel"
            aria-expanded={false}
            className="absolute right-4 top-4 z-10 flex items-center gap-2 border border-slate-200 bg-white px-3 py-2 text-sm font-medium shadow-md hover:bg-slate-50"
          >
            Hazard Triage
            <span className="bg-red-100 px-1.5 text-xs font-semibold text-red-700">
              {locationHazards.filter((h) => h.status !== "resolved").length}
            </span>
          </button>
        )}
      </main>

      <Sidebar
        states={STATES}
        state={state}
        onStateChange={changeState}
        cities={cities}
        citiesLoading={citiesLoading}
        citiesError={citiesError}
        city={city}
        onCityChange={changeCity}
        hazards={locationHazards}
        selected={selected}
        onSelect={selectHazard}
        onExit={exitHazard}
        open={panelOpen}
        onClose={() => setPanelOpen(false)}
      />
    </div>
  );
}

export default App;
