export type RiskLevelName =
  | "low"
  | "moderate"
  | "high"
  | "severe"
  | "no_travel";

export type CheckpointInterval = 10 | 25 | 50;

export interface RoutePlanRequest {
  origin: string;
  destination: string;
  departure_at: string;
  load_weight_lb: number;
  checkpoint_interval_miles: CheckpointInterval;
  origin_latitude?: number;
  origin_longitude?: number;
  destination_latitude?: number;
  destination_longitude?: number;
}

export interface PlaceSuggestion {
  label: string;
  latitude: number;
  longitude: number;
}

export interface CheckpointWeather {
  available: boolean;
  wind_mph: number | null;
  rain_in_hr: number | null;
  snow_in_hr: number | null;
  temperature_c: number | null;
  observed_at: string | null;
  source: string;
}

export interface Checkpoint {
  sequence: number;
  coordinate: { latitude: number; longitude: number };
  cumulative_miles: number;
  distance_from_previous_miles: number;
  arrival_at: string;
  weather: CheckpointWeather;
  hazards: {
    wind: RiskLevelName | null;
    rain: RiskLevelName | null;
    snow: RiskLevelName | null;
  };
  combined_risk: RiskLevelName | null;
  no_travel_reason: string | null;
}

export interface RiskSummary {
  low_miles: number;
  moderate_miles: number;
  high_miles: number;
  severe_miles: number;
  no_travel_miles: number;
  unknown_miles: number;
  average_risk: number;
  total_miles: number;
}

export interface RouteResult {
  id: string;
  label: string;
  source: string;
  geometry: [number, number][];
  distance_miles: number;
  duration_seconds: number;
  arrival_at: string;
  feasible: boolean;
  risk_summary: RiskSummary;
  checkpoints: Checkpoint[];
}

export interface HeatGridPoint {
  latitude: number;
  longitude: number;
  wind_mph: (number | null)[];
  rain_in_hr: (number | null)[];
  snow_in_hr: (number | null)[];
}

export interface HeatGrid {
  bounds: {
    south: number;
    north: number;
    west: number;
    east: number;
  } | null;
  rows: number;
  columns: number;
  spacing_latitude: number;
  spacing_longitude: number;
  points: HeatGridPoint[];
}

export interface PlaceInfo {
  query: string;
  label: string;
  latitude: number;
  longitude: number;
  source: string;
}

export interface ForecastCoverage {
  start: string;
  end: string;
  hours: number;
}

export interface RoutePlanResponse {
  request_id: string;
  generated_at: string;
  units: Record<string, string>;
  data_sources: { geocoding: string; routing: string; weather: string };
  origin: PlaceInfo;
  destination: PlaceInfo;
  departure_at: string;
  checkpoint_interval_miles: number;
  load_weight_lb: number;
  forecast_coverage: ForecastCoverage;
  forecast_times: string[];
  grid: HeatGrid;
  routes: RouteResult[];
  recommended_route_id: string;
  recommendation_reasons: string[];
  assumptions: string[];
  warnings: string[];
  weather_available: boolean;
}

export interface ApiErrorPayload {
  error: {
    code: string;
    message: string;
    details: Record<string, unknown>;
  };
}
