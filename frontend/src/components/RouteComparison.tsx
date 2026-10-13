import { formatClock, formatMiles, formatValue } from "../lib/format";
import { RISK_META, riskLabel } from "../lib/risk";
import { routeColor } from "../lib/variables";
import type { RouteResult } from "../types";
import { RouteCard } from "./RouteCard";

interface RouteComparisonProps {
  routes: RouteResult[];
  recommendedId: string;
  selectedId: string | null;
  onSelect: (id: string) => void;
  reasons: string[];
}

export function RouteComparison({
  routes,
  recommendedId,
  selectedId,
  onSelect,
  reasons,
}: RouteComparisonProps) {
  const selected = routes.find((route) => route.id === selectedId) ?? routes[0];

  return (
    <section className="comparison">
      <h2>Route options</h2>
      <div className="route-list">
        {routes.map((route, index) => (
          <RouteCard
            key={route.id}
            route={route}
            index={index}
            recommended={route.id === recommendedId}
            selected={route.id === selected?.id}
            onSelect={() => onSelect(route.id)}
          />
        ))}
      </div>

      <div className="card recommendation-card">
        <h3>Why this recommendation</h3>
        <ul className="reasons">
          {reasons.map((reason, index) => (
            <li key={index}>{reason}</li>
          ))}
        </ul>
      </div>

      {selected ? (
        <div className="card detail-card">
          <div className="detail-head">
            <span
              className="route-swatch"
              style={{
                backgroundColor: routeColor(
                  routes.findIndex((route) => route.id === selected.id),
                ),
              }}
            />
            <h3>{selected.label} checkpoints</h3>
          </div>
          <div className="table-scroll">
            <table className="checkpoint-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Mile</th>
                  <th>ETA</th>
                  <th>Wind</th>
                  <th>Rain</th>
                  <th>Snow</th>
                  <th>Risk</th>
                </tr>
              </thead>
              <tbody>
                {selected.checkpoints.map((checkpoint) => {
                  const level = checkpoint.combined_risk;
                  return (
                    <tr key={checkpoint.sequence}>
                      <td>{checkpoint.sequence}</td>
                      <td>{checkpoint.cumulative_miles.toFixed(0)}</td>
                      <td>{formatClock(checkpoint.arrival_at)}</td>
                      <td>
                        {checkpoint.weather.available
                          ? formatValue(checkpoint.weather.wind_mph)
                          : "-"}
                      </td>
                      <td>
                        {checkpoint.weather.available
                          ? formatValue(checkpoint.weather.rain_in_hr, 2)
                          : "-"}
                      </td>
                      <td>
                        {checkpoint.weather.available
                          ? formatValue(checkpoint.weather.snow_in_hr, 2)
                          : "-"}
                      </td>
                      <td>
                        <span
                          className="risk-chip"
                          style={{
                            borderColor: level ? RISK_META[level].color : "#8a8f98",
                            color: level ? RISK_META[level].color : "#8a8f98",
                          }}
                          title={checkpoint.no_travel_reason ?? undefined}
                        >
                          {level ? RISK_META[level].icon : "?"} {riskLabel(level)}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="detail-note">
            {formatMiles(selected.risk_summary.no_travel_miles)} no-travel,{" "}
            {formatMiles(selected.risk_summary.unknown_miles)} without forecast
            coverage.
          </p>
        </div>
      ) : null}
    </section>
  );
}
