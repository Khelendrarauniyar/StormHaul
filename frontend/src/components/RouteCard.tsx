import { formatClock, formatDuration, formatMiles } from "../lib/format";
import { RISK_META } from "../lib/risk";
import { routeColor } from "../lib/variables";
import type { RiskSummary, RouteResult } from "../types";

function RiskBar({ summary }: { summary: RiskSummary }) {
  const total = summary.total_miles || 1;
  const parts: { key: string; miles: number; color: string }[] = [
    { key: "low", miles: summary.low_miles, color: RISK_META.low.color },
    { key: "moderate", miles: summary.moderate_miles, color: RISK_META.moderate.color },
    { key: "high", miles: summary.high_miles, color: RISK_META.high.color },
    { key: "severe", miles: summary.severe_miles, color: RISK_META.severe.color },
    { key: "no_travel", miles: summary.no_travel_miles, color: RISK_META.no_travel.color },
    { key: "unknown", miles: summary.unknown_miles, color: "#8a8f98" },
  ];
  return (
    <div className="risk-bar" aria-hidden="true">
      {parts
        .filter((part) => part.miles > 0)
        .map((part) => (
          <span
            key={part.key}
            className="risk-bar-segment"
            style={{
              width: `${(part.miles / total) * 100}%`,
              backgroundColor: part.color,
            }}
          />
        ))}
    </div>
  );
}

interface RouteCardProps {
  route: RouteResult;
  index: number;
  recommended: boolean;
  selected: boolean;
  onSelect: () => void;
}

export function RouteCard({
  route,
  index,
  recommended,
  selected,
  onSelect,
}: RouteCardProps) {
  const summary = route.risk_summary;
  return (
    <button
      type="button"
      className={`route-card ${selected ? "is-selected" : ""}`}
      onClick={onSelect}
      aria-pressed={selected}
    >
      <div className="route-card-head">
        <span className="route-swatch" style={{ backgroundColor: routeColor(index) }} />
        <span className="route-card-title">{route.label}</span>
        {recommended ? <span className="badge badge-recommended">Recommended</span> : null}
        {!route.feasible ? <span className="badge badge-danger">No Travel</span> : null}
      </div>
      <div className="route-metrics">
        <span>
          <strong>{formatMiles(route.distance_miles)}</strong>
          <small>distance</small>
        </span>
        <span>
          <strong>{formatDuration(route.duration_seconds)}</strong>
          <small>duration</small>
        </span>
        <span>
          <strong>{formatMiles(summary.severe_miles)}</strong>
          <small>severe</small>
        </span>
        <span>
          <strong>{formatMiles(summary.high_miles)}</strong>
          <small>high</small>
        </span>
        <span>
          <strong>{summary.average_risk.toFixed(2)}</strong>
          <small>avg risk</small>
        </span>
      </div>
      <RiskBar summary={summary} />
      <div className="route-card-foot">
        <span>{route.checkpoints.length} checkpoints</span>
        <span>Arrives {formatClock(route.arrival_at)}</span>
      </div>
    </button>
  );
}
