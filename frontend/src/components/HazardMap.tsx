import "@arcgis/map-components/components/arcgis-map";
import "@arcgis/map-components/components/arcgis-zoom";
import Graphic from "@arcgis/core/Graphic.js";
import Point from "@arcgis/core/geometry/Point.js";
import FeatureLayer from "@arcgis/core/layers/FeatureLayer.js";
import { useEffect, useRef, useState, type RefObject } from "react";
import { INITIAL_VIEW } from "../data/areas";
import type { Hazard } from "../data/hazards";

interface HazardMapProps {
  hazards: Hazard[];
  selectedId: number | null;
  onSelect: (objectId: number | null) => void;
  mapRef: RefObject<HTMLArcgisMapElement | null>;
}

const marker = (color: string) => ({
  type: "simple-marker" as const,
  style: "circle" as const,
  size: 14,
  color,
  outline: { color: "white", width: 2 },
});

function buildHazardLayer(hazards: Hazard[]) {
  return new FeatureLayer({
    title: "Road hazards",
    objectIdField: "ObjectID",
    geometryType: "point",
    spatialReference: { wkid: 4326 },
    fields: [
      { name: "ObjectID", type: "oid" },
      { name: "hazard_type", type: "string" },
      { name: "severity", type: "string" },
      { name: "status", type: "string" },
      { name: "report_count", type: "integer" },
    ],
    source: hazards.map(
      (h) =>
        new Graphic({
          geometry: new Point({ longitude: h.lon, latitude: h.lat }),
          attributes: {
            ObjectID: h.objectId,
            hazard_type: h.hazard_type,
            severity: h.severity,
            status: h.status,
            report_count: h.report_count,
          },
        }),
    ),
    renderer: {
      type: "unique-value",
      valueExpression:
        "IIf($feature.status == 'resolved', 'resolved', $feature.severity)",
      uniqueValueInfos: [
        { value: "High", label: "High", symbol: marker("#dc2626") },
        { value: "Medium", label: "Medium", symbol: marker("#f59e0b") },
        { value: "Low", label: "Low", symbol: marker("#eab308") },
        { value: "resolved", label: "Resolved", symbol: marker("#16a34a") },
      ],
      defaultSymbol: marker("#64748b"),
    },
  });
}

function checkWebGL2(): boolean {
  try {
    const gl = document.createElement("canvas").getContext("webgl2");
    if (!gl) return false;
    gl.getExtension("WEBGL_lose_context")?.loseContext();
    return true;
  } catch {
    return false;
  }
}

const RETRY_MS = 1500;
const MAX_AUTO_RETRIES = 20;

function NoWebGLMessage({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="flex h-full items-center justify-center p-6">
      <div className="max-w-md border border-amber-200 bg-amber-50 p-5 text-sm text-amber-900 shadow-sm">
        <h2 className="text-base font-semibold">The map can't load in this browser</h2>
        <p className="mt-2">
          The map needs <strong>WebGL2</strong> (GPU graphics), which isn't available right now.
          The hazard list in the sidebar still works. This page keeps retrying, so if the GPU
          was just busy the map will appear by itself.
        </p>
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 border border-amber-300 bg-white px-3 py-1.5 font-medium hover:bg-amber-100"
        >
          Try again
        </button>
        <p className="mt-3 font-medium">If it never loads:</p>
        <ul className="mt-1 list-disc space-y-1 pl-5">
          <li>Turn on hardware / graphics acceleration in your browser settings and restart it.</li>
          <li>
            In Chrome, check <code className="bg-amber-100 px-1">chrome://gpu</code>; in Firefox,{" "}
            <code className="bg-amber-100 px-1">about:support</code>.
          </li>
          <li>Or open this page in a different browser.</li>
        </ul>
      </div>
    </div>
  );
}

export function HazardMap(props: HazardMapProps) {
  const [glReady, setGlReady] = useState(checkWebGL2);

  useEffect(() => {
    if (glReady) return;
    let tries = 0;
    const recheck = () => {
      if (checkWebGL2()) setGlReady(true);
    };
    const timer = window.setInterval(() => {
      tries += 1;
      recheck();
      if (tries >= MAX_AUTO_RETRIES) window.clearInterval(timer);
    }, RETRY_MS);
    const onVisible = () => {
      if (document.visibilityState === "visible") recheck();
    };
    document.addEventListener("visibilitychange", onVisible);
    window.addEventListener("focus", recheck);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisible);
      window.removeEventListener("focus", recheck);
    };
  }, [glReady]);

  if (!glReady) {
    return <NoWebGLMessage onRetry={() => setGlReady(checkWebGL2())} />;
  }
  return <HazardMapView {...props} />;
}

function HazardMapView({ hazards, selectedId, onSelect, mapRef }: HazardMapProps) {
  const layerRef = useRef<FeatureLayer | null>(null);
  const highlightRef = useRef<{ remove(): void } | null>(null);

  const handleReady = (event: CustomEvent) => {
    const mapEl = event.target as HTMLArcgisMapElement;
    if (!mapEl.ready || layerRef.current) return;
    const layer = buildHazardLayer(hazards);
    layerRef.current = layer;
    mapEl.map?.add(layer);
  };

  const handleClick = async (event: HTMLArcgisMapElement["arcgisViewClick"]) => {
    const mapEl = mapRef.current;
    const layer = layerRef.current;
    if (!mapEl || !layer) return;
    const response = await mapEl.hitTest(event.detail, { include: [layer] });
    const hit = response.results.find((r) => r.type === "graphic");
    onSelect(hit && "graphic" in hit ? (hit.graphic.attributes.ObjectID as number) : null);
  };

  useEffect(() => {
    const mapEl = mapRef.current;
    const layer = layerRef.current;
    highlightRef.current?.remove();
    highlightRef.current = null;
    if (!mapEl?.ready || !layer || selectedId == null) return;
    let cancelled = false;
    mapEl.whenLayerView(layer).then((layerView) => {
      if (!cancelled) highlightRef.current = layerView.highlight(selectedId);
    });
    return () => {
      cancelled = true;
    };
  }, [selectedId, mapRef]);

  return (
    <arcgis-map
      ref={mapRef}
      className="block h-full w-full"
      basemap="streets-vector"
      center={INITIAL_VIEW.center}
      zoom={INITIAL_VIEW.zoom}
      popupDisabled
      onarcgisViewReadyChange={handleReady}
      onarcgisViewClick={handleClick}
    >
      <arcgis-zoom slot="top-left" />
    </arcgis-map>
  );
}
