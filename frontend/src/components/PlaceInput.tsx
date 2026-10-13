import { useEffect, useRef, useState, type KeyboardEvent } from "react";

import { searchPlaces } from "../api/client";
import type { PlaceSuggestion } from "../types";

interface PlaceInputProps {
  value: string;
  onChange: (value: string) => void;
  onSelect: (place: PlaceSuggestion) => void;
  placeholder?: string;
}

export function PlaceInput({
  value,
  onChange,
  onSelect,
  placeholder,
}: PlaceInputProps) {
  const [suggestions, setSuggestions] = useState<PlaceSuggestion[]>([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const [loading, setLoading] = useState(false);
  const skipRef = useRef(false);
  const controllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (skipRef.current) {
      skipRef.current = false;
      return;
    }
    controllerRef.current?.abort();
    const query = value.trim();
    if (query.length < 2) {
      setSuggestions([]);
      setOpen(false);
      setLoading(false);
      return;
    }
    setLoading(true);
    const timer = setTimeout(async () => {
      const controller = new AbortController();
      controllerRef.current = controller;
      const results = await searchPlaces(query, controller.signal);
      if (controller.signal.aborted) {
        return;
      }
      setSuggestions(results);
      setActive(-1);
      setOpen(true);
      setLoading(false);
    }, 250);
    return () => {
      clearTimeout(timer);
      controllerRef.current?.abort();
    };
  }, [value]);

  const choose = (place: PlaceSuggestion) => {
    skipRef.current = true;
    onChange(place.label);
    onSelect(place);
    setSuggestions([]);
    setOpen(false);
    setActive(-1);
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (!open || suggestions.length === 0) {
      return;
    }
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActive((index) => (index + 1) % suggestions.length);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((index) => (index - 1 + suggestions.length) % suggestions.length);
    } else if (event.key === "Enter") {
      if (active >= 0 && active < suggestions.length) {
        event.preventDefault();
        choose(suggestions[active]);
      }
    } else if (event.key === "Escape") {
      setOpen(false);
      setActive(-1);
    }
  };

  return (
    <div className="place-input">
      <input
        type="text"
        value={value}
        placeholder={placeholder}
        autoComplete="off"
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={handleKeyDown}
        onFocus={() => {
          if (suggestions.length > 0) {
            setOpen(true);
          }
        }}
        onBlur={() => setTimeout(() => setOpen(false), 120)}
        required
      />
      {loading ? <span className="place-spinner" aria-hidden="true" /> : null}
      {open && suggestions.length > 0 ? (
        <ul className="suggestions" role="listbox">
          {suggestions.map((place, index) => (
            <li key={`${place.label}-${place.latitude}-${place.longitude}`}>
              <button
                type="button"
                role="option"
                aria-selected={index === active}
                className={index === active ? "suggestion active" : "suggestion"}
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => choose(place)}
                onMouseEnter={() => setActive(index)}
              >
                {place.label}
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
