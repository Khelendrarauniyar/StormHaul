import { useState, type FormEvent } from "react";

import type { CheckpointInterval, PlaceSuggestion, RoutePlanRequest } from "../types";
import { PlaceInput } from "./PlaceInput";

const INTERVALS: CheckpointInterval[] = [10, 25, 50];

function toLocalInput(date: Date): string {
  const pad = (value: number) => String(value).padStart(2, "0");
  return [
    date.getFullYear(),
    "-",
    pad(date.getMonth() + 1),
    "-",
    pad(date.getDate()),
    "T",
    pad(date.getHours()),
    ":",
    pad(date.getMinutes()),
  ].join("");
}

function defaultDeparture(): string {
  const date = new Date();
  date.setDate(date.getDate() + 1);
  date.setHours(8, 0, 0, 0);
  return toLocalInput(date);
}

interface RouteFormProps {
  onSubmit: (input: RoutePlanRequest) => void;
  loading: boolean;
}

export function RouteForm({ onSubmit, loading }: RouteFormProps) {
  const [origin, setOrigin] = useState("");
  const [originPlace, setOriginPlace] = useState<PlaceSuggestion | null>(null);
  const [destination, setDestination] = useState("");
  const [destinationPlace, setDestinationPlace] = useState<PlaceSuggestion | null>(
    null,
  );
  const [departure, setDeparture] = useState(defaultDeparture());
  const [load, setLoad] = useState(32000);
  const [interval, setInterval] = useState<CheckpointInterval>(25);

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    onSubmit({
      origin: origin.trim(),
      destination: destination.trim(),
      ...(originPlace
        ? {
            origin_latitude: originPlace.latitude,
            origin_longitude: originPlace.longitude,
          }
        : {}),
      ...(destinationPlace
        ? {
            destination_latitude: destinationPlace.latitude,
            destination_longitude: destinationPlace.longitude,
          }
        : {}),
      departure_at: new Date(departure).toISOString(),
      load_weight_lb: load,
      checkpoint_interval_miles: interval,
    });
  };

  return (
    <form className="card form" onSubmit={handleSubmit}>
      <h2>Trip details</h2>
      <label className="field">
        <span>Origin</span>
        <PlaceInput
          value={origin}
          onChange={(next) => {
            setOrigin(next);
            setOriginPlace(null);
          }}
          onSelect={setOriginPlace}
          placeholder="Denver, CO or 39.74,-104.98"
        />
      </label>
      <label className="field">
        <span>Destination</span>
        <PlaceInput
          value={destination}
          onChange={(next) => {
            setDestination(next);
            setDestinationPlace(null);
          }}
          onSelect={setDestinationPlace}
          placeholder="Salt Lake City, UT"
        />
      </label>
      <label className="field">
        <span>Departure</span>
        <input
          type="datetime-local"
          value={departure}
          onChange={(event) => setDeparture(event.target.value)}
          required
        />
      </label>
      <label className="field">
        <span>Load weight (lb)</span>
        <input
          type="number"
          min={1}
          max={500000}
          step={500}
          value={load}
          onChange={(event) => setLoad(Number(event.target.value))}
          required
        />
      </label>
      <label className="field">
        <span>Checkpoint spacing</span>
        <select
          value={interval}
          onChange={(event) =>
            setInterval(Number(event.target.value) as CheckpointInterval)
          }
        >
          {INTERVALS.map((value) => (
            <option key={value} value={value}>
              {value} miles
            </option>
          ))}
        </select>
      </label>
      <button type="submit" className="primary-button" disabled={loading}>
        {loading ? "Planning routes..." : "Plan routes"}
      </button>
    </form>
  );
}
