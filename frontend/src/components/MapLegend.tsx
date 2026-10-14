import { formatValue } from "../lib/format";
import { RISK_META, RISK_ORDER } from "../lib/risk";
import { VARIABLES, routeColor, type WeatherVariable } from "../lib/variables";
import type { RouteResult } from "../types";

interface MapLegendProps {
  routes: RouteResult[];
  recommendedId: string;
  variable: WeatherVariable;
  forecastLabel: string;
  weatherAvailable: boolean;
  heatDomain: [number, number] | null;
}

function legendDigits(variable: WeatherVariable): number {
  return variable === "wind" ? 0 : 2;
}

export function MapLegend({
  routes,
  recommendedId,
  variable,
  forecastLabel,
  weatherAvailable,
  heatDomain,
}: MapLegendProps) {
  const variableMeta = VARIABLES[variable];
  const digits = legendDigits(variable);
  const showScale = weatherAvailable && heatDomain !== null;
  const midpoint = heatDomain ? (heatDomain[0] + heatDomain[1]) / 2 : 0;

  return (
    <div className="map-legend">
      <div className="legend-section">
        <h4>Routes</h4>
        <ul>
          {routes.map((route, index) => (
            <li key={route.id}>
              <span
                className="legend-line"
                style={{ backgroundColor: routeColor(index) }}
              />
              <span>
                {route.label}
                {route.id === recommendedId ? " (recommended)" : ""}
              </span>
            </li>
          ))}
        </ul>
      </div>

      <div className="legend-section">
        <h4>Checkpoint risk</h4>
        <ul className="legend-risk">
          {RISK_ORDER.map((level) => (
            <li key={level}>
              <span
                className="legend-dot"
                style={{ backgroundColor: RISK_META[level].color }}
              />
              <span>{RISK_META[level].label}</span>
            </li>
          ))}
        </ul>
      </div>

      <div className="legend-section">
        <h4>
          {variableMeta.label} ({variableMeta.unit})
        </h4>
        {showScale ? (
          <>
            <div
              className="legend-gradient"
              style={{
                background: `linear-gradient(90deg, ${variableMeta.gradient.join(", ")})`,
              }}
            />
            <div className="legend-scale">
              <span>{formatValue(heatDomain![0], digits)}</span>
              <span>{formatValue(midpoint, digits)}</span>
              <span>{formatValue(heatDomain![1], digits)}</span>
            </div>
            <p className="legend-note">
              Forecast heat map for {forecastLabel}. Each cell is the {variableMeta.label.toLowerCase()} value on a grid covering the planned routes, scaled to the range above.
            </p>
          </>
        ) : (
          <p className="legend-note">Forecast unavailable for this request.</p>
        )}
      </div>
    </div>
  );
}
