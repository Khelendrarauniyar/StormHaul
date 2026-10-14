import type { HeatGrid } from "../types";
import { VARIABLES, type WeatherVariable } from "./variables";

export type HeatDomain = [number, number];

export function computeHeatDomain(
  grid: HeatGrid,
  variable: WeatherVariable,
): HeatDomain {
  const field = VARIABLES[variable].field;
  let min = Infinity;
  let max = -Infinity;
  for (const point of grid.points) {
    for (const value of point[field]) {
      if (value === null || value === undefined) {
        continue;
      }
      if (value < min) {
        min = value;
      }
      if (value > max) {
        max = value;
      }
    }
  }
  if (!Number.isFinite(min) || !Number.isFinite(max) || min === max) {
    return [0, VARIABLES[variable].max];
  }
  return [min, max];
}

export function heatColorExpression(
  domain: HeatDomain,
  gradient: string[],
): unknown[] {
  const [min, max] = domain;
  const span = max - min || 1;
  const expression: unknown[] = ["interpolate", ["linear"], ["get", "value"]];
  gradient.forEach((color, index) => {
    expression.push(min + (span * index) / (gradient.length - 1), color);
  });
  return expression;
}

export function buildHeatCells(
  grid: HeatGrid,
  variable: WeatherVariable,
  hour: number,
) {
  const field = VARIABLES[variable].field;
  const halfLatitude = grid.spacing_latitude / 2;
  const halfLongitude = grid.spacing_longitude / 2;
  const features = [];
  for (const point of grid.points) {
    const value = point[field][hour];
    if (value === null || value === undefined) {
      continue;
    }
    const west = point.longitude - halfLongitude;
    const east = point.longitude + halfLongitude;
    const south = point.latitude - halfLatitude;
    const north = point.latitude + halfLatitude;
    features.push({
      type: "Feature",
      properties: { value },
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [west, south],
            [east, south],
            [east, north],
            [west, north],
            [west, south],
          ],
        ],
      },
    });
  }
  return { type: "FeatureCollection", features };
}
