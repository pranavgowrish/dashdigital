import { useEffect, useState } from "react";
import type { UsState } from "../data/areas";
import type { CityOption } from "../data/cities";
import { CityPicker } from "./CityPicker";
import type { Hazard, HazardStatus, Severity } from "../data/hazards";

const SEVERITY_COLOR: Record<Severity, string> = {
  high: "#dc2626",
  medium: "#f59e0b",
  low: "#eab308",
};

const SEVERITY_LABEL: Record<Severity, string> = {
  high: "High",
  medium: "Medium",
  low: "Low",
};
const RESOLVED_COLOR = "#16a34a";

const STATUS_LABEL: Record<HazardStatus, string> = {
  open: "Open",
  dispatched: "Crew dispatched",
  resolved: "Resolved",
};

const pinColor = (h: Hazard) => (h.status === "resolved" ? RESOLVED_COLOR : SEVERITY_COLOR[h.severity]);

function SeverityTag({ hazard }: { hazard: Hazard }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-slate-700">
      <span className="h-2.5 w-2.5" style={{ background: pinColor(hazard) }} />
      {hazard.status === "resolved" ? "Resolved" : SEVERITY_LABEL[hazard.severity]}
    </span>
  );
}

const formatCoords = (h: Hazard) => `${h.lat.toFixed(5)}, ${h.lon.toFixed(5)}`;

const ticketId = (h: Hazard) => `HZ-${String(h.objectId).padStart(4, "0")}`;

function timeAgo(iso: string) {
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  const hours = Math.round(mins / 60);
  if (hours < 48) return `${hours} h ago`;
  return `${Math.round(hours / 24)} days ago`;
}

const label = (h: Hazard) => h.hazard_type.charAt(0).toUpperCase() + h.hazard_type.slice(1);
const formatTime = (iso: string) =>
  new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });

const SELECT_CLASS =
  "mt-1 w-full border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-200";
const LABEL_CLASS = "mt-3 block text-sm font-medium text-slate-700";

const DEFAULT_WIDTH = 384;
const MIN_WIDTH = 280;
const WIDTH_KEY = "triage-panel-width";
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
    return;
  }
}

function ResizeHandle({ width, onResize }: { width: number; onResize: (w: number) => void }) {
  const onPointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    e.preventDefault();
    const handle = e.currentTarget;
    handle.setPointerCapture(e.pointerId);
    const startX = e.clientX;
    const startWidth = width;
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";

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
  cities: CityOption[];
  citiesLoading: boolean;
  citiesError: string | null;
  city: CityOption | null;
  onCityChange: (city: CityOption | null) => void;
  hazards: Hazard[];
  selected: Hazard | null;
  onSelect: (objectId: number | null) => void;
  onExit: () => void;
  onDelete: (hazard: Hazard) => Promise<void>;
  onView3D: (hazard: Hazard) => Promise<void>;
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
  onDelete,
  onView3D,
}: SidebarProps) {
  const active = hazards.filter((h) => h.status !== "resolved").length;
  const high = hazards.filter((h) => h.status !== "resolved" && h.severity === "high").length;
  const placeName = city?.name ?? state?.name ?? "any location";
  const [width, setWidth] = useState(loadWidth);
  const [busy, setBusy] = useState(false);
  const resize = (w: number) => {
    setWidth(w);
    saveWidth(w);
  };

  return (
    <aside
      id="triage-panel"
      inert={!open || busy}
      aria-hidden={!open}
      style={{ width: open ? width : 0, maxWidth: "calc(100vw - 15rem)" }}
      className={`relative shrink-0 overflow-hidden bg-white ${open ? "border-l border-slate-200" : ""}`}
    >
     {open && !busy && <ResizeHandle width={width} onResize={resize} />}
     {busy && (
       <div
         aria-hidden
         className="absolute inset-0 z-40 flex cursor-wait items-center justify-center bg-slate-200/60"
       >
         <div className="flex items-center gap-2 border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 shadow-md">
           <span className="h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-slate-300 border-t-slate-700" />
           Building 3D view…
         </div>
       </div>
     )}
     <div
       className={`flex h-full flex-col ${busy ? "pointer-events-none select-none opacity-50" : ""}`}
       style={{ width, maxWidth: "calc(100vw - 15rem)" }}
     >
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

        <p className="mt-3 text-sm text-slate-600 tabular-nums">
          {hazards.length} {hazards.length === 1 ? "hazard" : "hazards"} · {active} open
          {high > 0 && <span className="text-red-700"> · {high} high priority</span>}
        </p>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {selected ? (
          <HazardDetail
            key={selected.id}
            hazard={selected}
            onBack={onExit}
            onDelete={onDelete}
            onView3D={onView3D}
            onBusyChange={setBusy}
          />
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
                      <SeverityTag hazard={h} />
                    </div>
                    <p className="truncate font-mono text-xs text-slate-600">{formatCoords(h)}</p>
                    <p className="text-xs text-slate-500 tabular-nums">
                      {ticketId(h)} · {timeAgo(h.detected_at)}
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

function HazardDetail({
  hazard,
  onBack,
  onDelete,
  onView3D,
  onBusyChange,
}: {
  hazard: Hazard;
  onBack: () => void;
  onDelete: (hazard: Hazard) => Promise<void>;
  onView3D: (hazard: Hazard) => Promise<void>;
  onBusyChange: (busy: boolean) => void;
}) {
  const [copied, setCopied] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [view3DState, setView3DState] = useState<"idle" | "loading" | "done">("idle");
  const [view3DError, setView3DError] = useState<string | null>(null);

  useEffect(() => () => onBusyChange(false), [onBusyChange]);

  const view3D = () => {
    setView3DState("loading");
    setView3DError(null);
    onBusyChange(true);
    onView3D(hazard)
      .then(() => {
        setView3DState("done");
        setTimeout(() => setView3DState("idle"), 10000);
      })
      .catch((err: Error) => {
        setView3DError(err.message || "3D render failed");
        setView3DState("idle");
      })
      .finally(() => onBusyChange(false));
  };

  const confirmDelete = () => {
    setDeleting(true);
    setDeleteError(null);
    onDelete(hazard).catch((err: Error) => {
      setDeleteError(err.message || "Delete failed");
      setDeleting(false);
    });
  };
  const coords = formatCoords(hazard);
  const copyCoords = () => {
    navigator.clipboard
      ?.writeText(coords)
      .then(() => {
        setCopied(true);
        setTimeout(() => setCopied(false), 1200);
      })
      .catch(() => {});
  };

  return (
    <div>
      <div className="flex items-center justify-between gap-2 border-b border-slate-200 px-4 py-2 text-sm">
        <button
          type="button"
          onClick={onBack}
          aria-label="Back to hazard list"
          title="Back to hazard list"
          className="-ml-1 flex items-center gap-1.5 border border-slate-300 bg-white px-2.5 py-1.5 font-medium text-slate-700 hover:bg-slate-50 hover:text-slate-950 focus:outline-none focus:ring-2 focus:ring-blue-200"
        >
          <span aria-hidden className="text-base leading-none">&larr;</span>
          Back
        </button>
        <span className="font-mono text-xs text-slate-500">{ticketId(hazard)}</span>
      </div>

      <figure className="relative bg-black">
        <img
          src={hazard.image_url}
          alt={`Dashcam crop of ${hazard.hazard_type} at ${coords}`}
          className="aspect-3/2 w-full object-cover"
        />
        <figcaption className="absolute inset-x-0 bottom-0 flex justify-end bg-black/55 px-2 py-1 font-mono text-[11px] text-white/90">
          <span>{hazard.detected_at.replace("T", " ").replace("Z", " UTC")}</span>
        </figcaption>
      </figure>

      <div className="border-l-4 px-4 py-3" style={{ borderColor: pinColor(hazard) }}>
        <div className="flex items-baseline justify-between gap-3">
          <h2 className="text-base font-semibold">{label(hazard)}</h2>
          <SeverityTag hazard={hazard} />
        </div>
      </div>

      <dl className="mt-2 divide-y divide-slate-100 border-y border-slate-100 text-sm">
        <Row term="Status">{STATUS_LABEL[hazard.status]}</Row>
        <Row term="Detected">
          {formatTime(hazard.detected_at)}
          <span className="text-slate-500"> ({timeAgo(hazard.detected_at)})</span>
        </Row>
        <Row term="Location">
          <span className="font-mono text-xs">{coords}</span>
          <button
            type="button"
            onClick={copyCoords}
            className="ml-2 text-xs text-slate-500 underline-offset-2 hover:text-slate-900 hover:underline"
          >
            {copied ? "Copied" : "Copy"}
          </button>
        </Row>
      </dl>

      <div className="px-4 pt-4">
        <button
          type="button"
          onClick={view3D}
          disabled={view3DState !== "idle"}
          className="border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50 disabled:opacity-60"
        >
          {view3DState === "loading" ? "Loading…" : view3DState === "done" ? "Done!" : "View in 3D"}
        </button>
        {view3DError && <p className="mt-2 text-sm text-red-700">{view3DError}</p>}
      </div>

      <div className="px-4 py-4">
        {!confirming ? (
          <button
            type="button"
            onClick={() => setConfirming(true)}
            className="border border-red-300 px-3 py-1.5 text-sm text-red-700 hover:bg-red-50"
          >
            Delete hazard
          </button>
        ) : (
          <div className="border border-red-200 bg-red-50 p-3 text-sm">
            <p className="text-red-900">
              Permanently delete {ticketId(hazard)} from the database? This can't be undone.
            </p>
            <div className="mt-2 flex gap-2">
              <button
                type="button"
                onClick={confirmDelete}
                disabled={deleting}
                className="bg-red-600 px-3 py-1.5 font-medium text-white hover:bg-red-700 disabled:opacity-60"
              >
                {deleting ? "Deleting…" : "Yes, delete"}
              </button>
              <button
                type="button"
                onClick={() => {
                  setConfirming(false);
                  setDeleteError(null);
                }}
                disabled={deleting}
                className="border border-slate-300 bg-white px-3 py-1.5 text-slate-700 hover:bg-slate-50"
              >
                Cancel
              </button>
            </div>
            {deleteError && <p className="mt-2 text-red-700">{deleteError}</p>}
          </div>
        )}
      </div>
    </div>
  );
}

function Row({ term, children }: { term: string; children: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 px-4 py-2">
      <dt className="shrink-0 text-slate-500">{term}</dt>
      <dd className="text-right text-slate-900 tabular-nums">{children}</dd>
    </div>
  );
}
