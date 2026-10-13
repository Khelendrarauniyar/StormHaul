import { useState } from "react";

import { ForecastControl } from "./components/ForecastControl";
import { MapLegend } from "./components/MapLegend";
import { RouteComparison } from "./components/RouteComparison";
import { RouteForm } from "./components/RouteForm";
import { StatusBanner } from "./components/StatusBanner";
import { TopBar } from "./components/TopBar";
import { useRoutePlan } from "./hooks/useRoutePlan";
import { formatClock } from "./lib/format";
import type { WeatherVariable } from "./lib/variables";
import { RouteMap } from "./map/RouteMap";
import type { RoutePlanRequest, RoutePlanResponse } from "./types";

export default function App() {
  const [plan, setPlan] = useState<RoutePlanResponse | null>(null);
  const [selectedRouteId, setSelectedRouteId] = useState<string | null>(null);
  const [forecastHour, setForecastHour] = useState(0);
  const [variable, setVariable] = useState<WeatherVariable>("wind");
  const { status, error, run, reset } = useRoutePlan();

  const handlePlan = async (input: RoutePlanRequest) => {
    const result = await run(input);
    if (result) {
      setPlan(result);
      setSelectedRouteId(result.recommended_route_id);
      setForecastHour(0);
    }
  };

  const handleReset = () => {
    setPlan(null);
    setSelectedRouteId(null);
    setForecastHour(0);
    reset();
  };

  const forecastLabel = plan
    ? formatClock(
        plan.forecast_times[
          Math.min(forecastHour, Math.max(0, plan.forecast_times.length - 1))
        ],
      )
    : "";

  return (
    <div className="app">
      <TopBar
        onReset={handleReset}
        busy={status === "loading"}
        dataSource={plan?.data_sources.routing}
      />

      <div className="layout">
        <aside className="side-panel">
          <RouteForm onSubmit={handlePlan} loading={status === "loading"} />

          {error ? (
            <StatusBanner tone="error" title="Request failed">
              <p>{error}</p>
            </StatusBanner>
          ) : null}

          {plan && plan.warnings.length > 0 ? (
            <StatusBanner tone="warning" title="Notes">
              <ul className="tight-list">
                {plan.warnings.map((warning, index) => (
                  <li key={index}>{warning}</li>
                ))}
              </ul>
            </StatusBanner>
          ) : null}

          {plan ? (
            <>
              <RouteComparison
                routes={plan.routes}
                recommendedId={plan.recommended_route_id}
                selectedId={selectedRouteId}
                onSelect={setSelectedRouteId}
                reasons={plan.recommendation_reasons}
              />

              <details className="card assumptions">
                <summary>Data sources &amp; assumptions</summary>
                <p className="assumptions-line">
                  Routing: {plan.data_sources.routing} &middot; Geocoding:{" "}
                  {plan.data_sources.geocoding} &middot; Weather:{" "}
                  {plan.data_sources.weather}
                </p>
                <ul className="tight-list">
                  {plan.assumptions.map((assumption, index) => (
                    <li key={index}>{assumption}</li>
                  ))}
                </ul>
              </details>
            </>
          ) : null}
        </aside>

        <main className="canvas">
          <RouteMap
            routes={plan?.routes ?? []}
            corridor={plan?.corridor ?? []}
            recommendedId={plan?.recommended_route_id ?? ""}
            selectedRouteId={selectedRouteId}
            onSelectRoute={setSelectedRouteId}
            variable={variable}
            forecastHour={forecastHour}
          />

          {!plan && status !== "loading" ? (
            <div className="canvas-empty">
              <h2>Plan a weather-aware route</h2>
              <p>
                Enter an origin, destination, departure time and load weight to
                compare three alternatives against checkpoint-time wind, rain and
                snow risk.
              </p>
            </div>
          ) : null}

          {status === "loading" ? (
            <div className="canvas-loading">
              <span className="spinner" aria-hidden="true" />
              Planning routes and sampling forecast weather...
            </div>
          ) : null}

          {plan ? (
            <>
              <MapLegend
                routes={plan.routes}
                recommendedId={plan.recommended_route_id}
                selectedRouteId={selectedRouteId}
                variable={variable}
                forecastLabel={forecastLabel}
                weatherAvailable={plan.weather_available}
              />
              <div className="forecast-dock">
                <ForecastControl
                  times={plan.forecast_times}
                  hour={forecastHour}
                  onHourChange={setForecastHour}
                  variable={variable}
                  onVariableChange={setVariable}
                  coverage={plan.forecast_coverage}
                  weatherAvailable={plan.weather_available}
                />
              </div>
            </>
          ) : null}
        </main>
      </div>
    </div>
  );
}
