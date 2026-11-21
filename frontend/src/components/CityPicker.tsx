import { useId, useState } from "react";
import type { CityOption } from "../data/cities";

const MAX_RESULTS = 50;

interface CityPickerProps {
  stateName: string;
  cities: CityOption[];
  loading: boolean;
  error: string | null;
  value: CityOption | null;
  onChange: (city: CityOption | null) => void;
}

export function CityPicker({ stateName, cities, loading, error, value, onChange }: CityPickerProps) {
  const listId = useId();
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);

  const q = query.trim().toLowerCase();
  const matches = (
    q
      ? [
          ...cities.filter((c) => c.name.toLowerCase().startsWith(q)),
          ...cities.filter((c) => !c.name.toLowerCase().startsWith(q) && c.name.toLowerCase().includes(q)),
        ]
      : [...cities].sort((a, b) => b.population - a.population) // biggest first when empty
  ).slice(0, MAX_RESULTS);

  const choose = (city: CityOption | null) => {
    onChange(city);
    setQuery("");
    setOpen(false);
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setOpen(true);
      setActive((i) => Math.min(i + 1, matches.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter" && open && matches[active]) {
      e.preventDefault();
      choose(matches[active]);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  };

  const placeholder = loading
    ? "Loading cities…"
    : error
      ? "Couldn't load cities"
      : value
        ? value.name
        : `All of ${stateName} — search ${cities.length.toLocaleString()} places`;

  return (
    <div className="relative mt-1">
      <div className="flex gap-2">
        <input
          type="text"
          role="combobox"
          aria-label="City"
          aria-expanded={open}
          aria-controls={listId}
          aria-autocomplete="list"
          disabled={loading || !!error}
          value={query}
          placeholder={placeholder}
          onChange={(e) => {
            setQuery(e.target.value);
            setActive(0);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 120)}
          onKeyDown={onKeyDown}
          className={`w-full border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-200 disabled:bg-slate-50 ${
            value ? "placeholder:text-slate-900" : ""
          }`}
        />
        {value && (
          <button
            type="button"
            onClick={() => choose(null)}
            className="shrink-0 border border-slate-300 px-3 text-sm text-slate-600 hover:bg-slate-50"
            title={`Show all of ${stateName}`}
          >
            Clear
          </button>
        )}
      </div>

      {error && <p className="mt-1 text-xs text-red-600">{error}</p>}

      {open && !loading && !error && (
        <ul
          id={listId}
          role="listbox"
          className="absolute z-20 mt-1 max-h-72 w-full overflow-y-auto border border-slate-200 bg-white py-1 shadow-lg"
        >
          {matches.length === 0 ? (
            <li className="px-3 py-2 text-sm text-slate-500">No places match “{query}”.</li>
          ) : (
            matches.map((c, i) => (
              <li
                key={c.id}
                role="option"
                aria-selected={i === active}
                onMouseDown={(e) => {
                  e.preventDefault();
                  choose(c);
                }}
                onMouseEnter={() => setActive(i)}
                className={`flex cursor-pointer items-baseline justify-between gap-2 px-3 py-1.5 text-sm ${
                  i === active ? "bg-blue-50" : ""
                }`}
              >
                <span className="truncate">{c.name}</span>
                <span className="shrink-0 text-xs text-slate-400">
                  {c.kind === "Census Designated Place" ? "CDP · " : ""}
                  {c.population.toLocaleString()}
                </span>
              </li>
            ))
          )}
        </ul>
      )}
    </div>
  );
}
