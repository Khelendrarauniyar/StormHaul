import { formatClock } from "../lib/format";
import { VARIABLE_LIST, type WeatherVariable } from "../lib/variables";
import type { ForecastCoverage } from "../types";

interface ForecastControlProps {
  times: string[];
  hour: number;
  onHourChange: (hour: number) => void;
  variable: WeatherVariable;
  onVariableChange: (variable: WeatherVariable) => void;
  coverage: ForecastCoverage;
  weatherAvailable: boolean;
  heatmapVisible: boolean;
  onToggleHeatmap: (visible: boolean) => void;
}

export function ForecastControl({
  times,
  hour,
  onHourChange,
  variable,
  onVariableChange,
  coverage,
  weatherAvailable,
  heatmapVisible,
  onToggleHeatmap,
}: ForecastControlProps) {
  const maxHour = Math.max(0, times.length - 1);
  const currentTime = times[Math.min(hour, maxHour)] ?? coverage.start;

  return (
    <div className="forecast-control">
      <div className="forecast-head">
        <strong>Forecast time</strong>
        <span>{formatClock(currentTime)}</span>
        <span className="forecast-offset">
          T+{hour}h of {coverage.hours}h
        </span>
      </div>
      <input
        type="range"
        min={0}
        max={maxHour}
        step={1}
        value={Math.min(hour, maxHour)}
        onChange={(event) => onHourChange(Number(event.target.value))}
        disabled={!weatherAvailable}
        aria-label="Forecast hour"
      />
      <div className="forecast-variables">
        {VARIABLE_LIST.map((meta) => (
          <button
            key={meta.key}
            type="button"
            className={variable === meta.key ? "chip is-active" : "chip"}
            onClick={() => onVariableChange(meta.key)}
          >
            {meta.label}
          </button>
        ))}
      </div>
      <label className="heat-toggle">
        <input
          type="checkbox"
          checked={heatmapVisible}
          onChange={(event) => onToggleHeatmap(event.target.checked)}
          disabled={!weatherAvailable}
        />
        Weather heat map
      </label>
      {!weatherAvailable ? (
        <p className="forecast-warning">
          Forecast coverage is unavailable for this request; the slider is disabled.
        </p>
      ) : null}
    </div>
  );
}
