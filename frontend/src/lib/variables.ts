export const ROUTE_COLORS = ["#1565c0", "#00897b", "#6a1b9a", "#c2185b"];

export function routeColor(index: number): string {
  return ROUTE_COLORS[index % ROUTE_COLORS.length];
}

export type WeatherVariable = "wind" | "rain" | "snow";

export interface VariableMeta {
  key: WeatherVariable;
  label: string;
  unit: string;
  field: "wind_mph" | "rain_in_hr" | "snow_in_hr";
  max: number;
  gradient: string[];
}

export const VARIABLES: Record<WeatherVariable, VariableMeta> = {
  wind: {
    key: "wind",
    label: "Wind speed",
    unit: "mph",
    field: "wind_mph",
    max: 60,
    gradient: ["#2c7bb6", "#abd9e9", "#ffffbf", "#fdae61", "#d7191c"],
  },
  rain: {
    key: "rain",
    label: "Rain rate",
    unit: "in/hr",
    field: "rain_in_hr",
    max: 1.0,
    gradient: ["#c6dbef", "#6baed6", "#3182bd", "#08519c", "#08306b"],
  },
  snow: {
    key: "snow",
    label: "Snow rate",
    unit: "in/hr",
    field: "snow_in_hr",
    max: 3.0,
    gradient: ["#e0f3db", "#ccebc5", "#a8ddb5", "#43a2ca", "#0868ac"],
  },
};

export const VARIABLE_LIST: VariableMeta[] = [
  VARIABLES.wind,
  VARIABLES.rain,
  VARIABLES.snow,
];
