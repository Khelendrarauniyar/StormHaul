import { RISK_META, RISK_ORDER } from "../lib/risk";
import { VARIABLES, routeColor, type WeatherVariable } from "../lib/variables";
import type { RouteResult } from "../types";

interface MapLegendProps {
  routes: RouteResult[];
  recommendedId: string;
  selectedRouteId: string | null;
  variable: WeatherVariable;
  forecastLabel: string;
  weatherAvailable: boolean;
}

export function MapLegend({
  routes,
  recommendedId,
  selectedRouteId,
  variable,
  forecastLabel,
  weatherAvailable,
}: MapLegendProps) {
  const variableMeta = VARIABLES[variable];
  const selected = routes.find((route) => route.id === selectedRouteId);

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
        {weatherAvailable ? (
          <>
            <div
              className="legend-gradient"
              style={{
                background: `linear-gradient(90deg, ${variableMeta.gradient.join(", ")})`,
              }}
            />
            <div className="legend-scale">
              <span>0</span>
              <span>{variableMeta.max}</span>
            </div>
            <p className="legend-note">
              Corridor heatmap for {selected?.label ?? "selected route"} at{" "}
              {forecastLabel}. Values are sampled, not a high-resolution model.
            </p>
          </>
        ) : (
          <p className="legend-note">Forecast unavailable for this request.</p>
        )}
      </div>
    </div>
  );
}
