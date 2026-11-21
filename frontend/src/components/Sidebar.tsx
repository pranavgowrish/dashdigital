import { useState } from "react";
import type { UsState } from "../data/areas";
import type { CityOption } from "../data/cities";
import { CityPicker } from "./CityPicker";
import type { Hazard, HazardStatus, Severity } from "../data/hazards";

const SEVERITY_STYLES: Record<Severity, string> = {
  High: "bg-red-100 text-red-700 ring-red-200",
  Medium: "bg-amber-100 text-amber-700 ring-amber-200",
  Low: "bg-yellow-100 text-yellow-800 ring-yellow-200",
};

const STATUS_STYLES: Record<HazardStatus, string> = {
  open: "bg-slate-100 text-slate-700",
  dispatched: "bg-blue-100 text-blue-700",
  resolved: "bg-green-100 text-green-700",
};

function SeverityBadge({ hazard }: { hazard: Hazard }) {
  if (hazard.status === "resolved") {
    return (
      <span className="bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700 ring-1 ring-green-200">
        Resolved
      </span>
    );
  }
  return (
    <span
      className={`px-2 py-0.5 text-xs font-medium ring-1 ${SEVERITY_STYLES[hazard.severity]}`}
    >
      {hazard.severity}
    </span>
  );
}

const label = (h: Hazard) => h.hazard_type.charAt(0).toUpperCase() + h.hazard_type.slice(1);
const formatTime = (iso: string) =>
  new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });

const SELECT_CLASS =
  "mt-1 w-full border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-200";
const LABEL_CLASS = "mt-3 block text-xs font-medium uppercase tracking-wide text-slate-500";

const DEFAULT_WIDTH = 384;
const MIN_WIDTH = 280;
const WIDTH_KEY = "triage-panel-width";
/** Never let the panel take more than 75% of the window, so the map stays usable. */
const maxWidth = () => Math.max(MIN_WIDTH, Math.round(window.innerWidth * 0.75));
const clampWidth = (w: number) => Math.min(Math.max(w, MIN_WIDTH), maxWidth());

function loadWidth() {
  try {
    const saved = Number(localStorage.getItem(WIDTH_KEY));
    return saved ? clampWidth(saved) : DEFAULT_WIDTH;
  } catch {
    return DEFAULT_WIDTH;
  }
}

function saveWidth(w: number) {
  try {
    localStorage.setItem(WIDTH_KEY, String(w));
  } catch {
    // storage unavailable (private mode etc.): width just won't be remembered
  }
}

/** Drag handle on the panel's left edge. Also works with arrow keys; double-click resets. */
function ResizeHandle({ width, onResize }: { width: number; onResize: (w: number) => void }) {
  const onPointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    e.preventDefault();
    const handle = e.currentTarget;
    handle.setPointerCapture(e.pointerId);
    const startX = e.clientX;
    const startWidth = width;
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";

    // The panel sits on the right, so dragging left (smaller clientX) makes it wider.
    const onMove = (ev: PointerEvent) => onResize(clampWidth(startWidth + (startX - ev.clientX)));
    const onUp = () => {
      handle.removeEventListener("pointermove", onMove);
      handle.removeEventListener("pointerup", onUp);
      handle.removeEventListener("pointercancel", onUp);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
    handle.addEventListener("pointermove", onMove);
    handle.addEventListener("pointerup", onUp);
    handle.addEventListener("pointercancel", onUp);
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    const step = e.shiftKey ? 64 : 16;
    if (e.key === "ArrowLeft") onResize(clampWidth(width + step));
    else if (e.key === "ArrowRight") onResize(clampWidth(width - step));
    else return;
    e.preventDefault();
  };

  return (
    <div
      role="separator"
      aria-orientation="vertical"
      aria-label="Resize Hazard Triage panel"
      aria-valuenow={width}
      aria-valuemin={MIN_WIDTH}
      tabIndex={0}
      title="Drag to resize · double-click to reset"
      onPointerDown={onPointerDown}
      onKeyDown={onKeyDown}
      onDoubleClick={() => onResize(DEFAULT_WIDTH)}
      className="absolute inset-y-0 left-0 z-30 w-1.5 cursor-col-resize bg-transparent hover:bg-blue-400 focus:bg-blue-500 focus:outline-none active:bg-blue-500"
    />
  );
}

interface SidebarProps {
  states: UsState[];
  state: UsState | null;
  onStateChange: (code: string | null) => void;
  cities: CityOption[]; // places in the selected state
  citiesLoading: boolean;
  citiesError: string | null;
  city: CityOption | null;
  onCityChange: (city: CityOption | null) => void;
  hazards: Hazard[];
  selected: Hazard | null;
  onSelect: (objectId: number | null) => void;
  /** Leave the hazard detail view (App zooms the map back to where it was). */
  onExit: () => void;
  open: boolean;
  onClose: () => void;
}

export function Sidebar({
  open,
  onClose,
  states,
  state,
  onStateChange,
  cities,
  citiesLoading,
  citiesError,
  city,
  onCityChange,
  hazards,
  selected,
  onSelect,
  onExit,
}: SidebarProps) {
  const active = hazards.filter((h) => h.status !== "resolved").length;
  const high = hazards.filter((h) => h.status !== "resolved" && h.severity === "High").length;
  const placeName = city?.name ?? state?.name ?? "any location";
  const [width, setWidth] = useState(loadWidth);
  const resize = (w: number) => {
    setWidth(w);
    saveWidth(w);
  };

  return (
    // Closed = zero width (kept mounted so the city search and selection survive closing).
    <aside
      id="triage-panel"
      inert={!open}
      aria-hidden={!open}
      style={{ width: open ? width : 0, maxWidth: "calc(100vw - 15rem)" }}
      className={`relative shrink-0 overflow-hidden bg-white ${open ? "border-l border-slate-200" : ""}`}
    >
     {open && <ResizeHandle width={width} onResize={resize} />}
     <div className="flex h-full flex-col" style={{ width, maxWidth: "calc(100vw - 15rem)" }}>
      <header className="border-b border-slate-200 p-4">
        <div className="flex items-center justify-between">
          <h1 className="text-lg font-semibold">Hazard Triage</h1>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close Hazard Triage panel"
            title="Close panel"
            className="-mr-1 px-2 py-1 text-xl leading-none text-slate-500 hover:bg-slate-100 hover:text-slate-900"
          >
            ×
          </button>
        </div>

        <label htmlFor="state" className={LABEL_CLASS}>
          State
        </label>
        <select
          id="state"
          value={state?.code ?? ""}
          onChange={(e) => onStateChange(e.target.value || null)}
          className={SELECT_CLASS}
        >
          <option value="">Select a state…</option>
          {states.map((s) => (
            <option key={s.code} value={s.code}>
              {s.name}
            </option>
          ))}
        </select>

        {state && (
          <>
            <span className={LABEL_CLASS}>City</span>
            <CityPicker
              key={state.code}
              stateName={state.name}
              cities={cities}
              loading={citiesLoading}
              error={citiesError}
              value={city}
              onChange={onCityChange}
            />
          </>
        )}

        <div className="mt-3 grid grid-cols-3 gap-2 text-center">
          <Stat value={hazards.length} label="Total" />
          <Stat value={active} label="Active" />
          <Stat value={high} label="High" accent />
        </div>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {selected ? (
          <HazardDetail hazard={selected} onBack={onExit} />
        ) : hazards.length === 0 ? (
          <p className="p-4 text-sm text-slate-500">No hazards reported in {placeName}.</p>
        ) : (
          <ul className="divide-y divide-slate-100">
            {hazards.map((h) => (
              <li key={h.objectId}>
                <button
                  type="button"
                  onClick={() => onSelect(h.objectId)}
                  className="flex w-full items-center gap-3 p-3 text-left hover:bg-slate-50"
                >
                  <img
                    src={h.image_url}
                    alt=""
                    className="h-14 w-20 shrink-0 object-cover"
                  />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium">{label(h)}</span>
                      <SeverityBadge hazard={h} />
                    </div>
                    <p className="truncate text-sm text-slate-500">{h.street}</p>
                    <p className="text-xs text-slate-400">
                      {h.report_count} report{h.report_count === 1 ? "" : "s"}
                    </p>
                  </div>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
     </div>
    </aside>
  );
}

function Stat({ value, label, accent }: { value: number; label: string; accent?: boolean }) {
  return (
    <div className="bg-slate-50 py-2">
      <div className={`text-lg font-semibold ${accent ? "text-red-600" : ""}`}>{value}</div>
      <div className="text-xs text-slate-500">{label}</div>
    </div>
  );
}

function HazardDetail({ hazard, onBack }: { hazard: Hazard; onBack: () => void }) {
  return (
    <div className="p-4">
      <button
        type="button"
        onClick={onBack}
        className="text-sm font-medium text-blue-600 hover:text-blue-800"
      >
        Exit
      </button>

      <img
        src={hazard.image_url}
        alt={`Dashcam crop of ${hazard.hazard_type} on ${hazard.street}`}
        className="mt-3 aspect-[3/2] w-full object-cover"
      />

      <div className="mt-3 flex items-center justify-between">
        <h2 className="text-lg font-semibold">{label(hazard)}</h2>
        <SeverityBadge hazard={hazard} />
      </div>
      <p className="text-sm text-slate-500">{hazard.street}</p>

      <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
        <Field term="Status">
          <span className={`px-1.5 py-0.5 text-xs font-medium capitalize ${STATUS_STYLES[hazard.status]}`}>
            {hazard.status}
          </span>
        </Field>
        <Field term="Reports">{hazard.report_count}</Field>
        <Field term="Confidence">{Math.round(hazard.confidence * 100)}%</Field>
        <Field term="Device">{hazard.device_id}</Field>
        <Field term="Detected">{formatTime(hazard.detected_at)}</Field>
        <Field term="Coordinates">
          {hazard.lat.toFixed(5)}, {hazard.lon.toFixed(5)}
        </Field>
      </dl>
    </div>
  );
}

function Field({ term, children }: { term: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-slate-400">{term}</dt>
      <dd className="mt-0.5 text-slate-800">{children}</dd>
    </div>
  );
}
