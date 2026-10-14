import { useEffect, useRef, useState } from "react";
import maplibregl, {
  type GeoJSONSource,
  type Map as MapLibreMap,
  NavigationControl,
  Popup,
} from "maplibre-gl";

import { formatClock, formatValue } from "../lib/format";
import { buildHeatCells, heatColorExpression } from "../lib/heat";
import { RISK_META, riskLabel } from "../lib/risk";
import { VARIABLES, routeColor, type WeatherVariable } from "../lib/variables";
import type { HeatGrid, RiskLevelName, RouteResult } from "../types";
import { MAP_STYLE } from "./mapStyle";
import "maplibre-gl/dist/maplibre-gl.css";

interface RouteMapProps {
  routes: RouteResult[];
  grid: HeatGrid | null;
  heatDomain: [number, number];
  showHeatmap: boolean;
  recommendedId: string;
  selectedRouteId: string | null;
  onSelectRoute: (id: string) => void;
  variable: WeatherVariable;
  forecastHour: number;
}

const ROUTE_LAYER_PREFIXES = ["route-line-", "checkpoint-circle-", "endpoint-"];
const HEAT_PREFIX = "heat-grid-";

function escapeHtml(value: unknown): string {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function removeLayersAndSources(map: MapLibreMap, prefixes: string[]) {
  const style = map.getStyle();
  if (!style?.layers) {
    return;
  }
  for (const layer of style.layers) {
    if (prefixes.some((prefix) => layer.id.startsWith(prefix))) {
      if (map.getLayer(layer.id)) {
        map.removeLayer(layer.id);
      }
    }
  }
  const sources = style.sources ?? {};
  for (const sourceId of Object.keys(sources)) {
    if (prefixes.some((prefix) => sourceId.startsWith(prefix))) {
      if (map.getSource(sourceId)) {
        map.removeSource(sourceId);
      }
    }
  }
}

function firstLayerId(map: MapLibreMap, prefixes: string[]): string | undefined {
  const style = map.getStyle();
  if (!style?.layers) {
    return undefined;
  }
  return style.layers.find((layer) =>
    prefixes.some((prefix) => layer.id.startsWith(prefix)),
  )?.id;
}

function setSource(map: MapLibreMap, id: string, data: unknown) {
  const existing = map.getSource(id) as GeoJSONSource | undefined;
  if (existing) {
    existing.setData(data as never);
  } else {
    map.addSource(id, { type: "geojson", data: data as never });
  }
}

function buildRouteLine(route: RouteResult) {
  return {
    type: "Feature",
    properties: { route_id: route.id, label: route.label },
    geometry: { type: "LineString", coordinates: route.geometry },
  };
}

function riskMatchExpression(fallback: string) {
  const expression: unknown[] = ["match", ["get", "risk"]];
  (Object.keys(RISK_META) as RiskLevelName[]).forEach((level) => {
    expression.push(level, RISK_META[level].color);
  });
  expression.push(fallback);
  return expression;
}

function buildCheckpoints(route: RouteResult) {
  return {
    type: "FeatureCollection",
    features: route.checkpoints.map((checkpoint) => ({
      type: "Feature",
      properties: {
        route_id: route.id,
        route_label: route.label,
        sequence: checkpoint.sequence,
        mile: `${checkpoint.cumulative_miles.toFixed(0)} mi`,
        eta: formatClock(checkpoint.arrival_at),
        wind:
          checkpoint.weather.wind_mph === null
            ? "n/a"
            : `${formatValue(checkpoint.weather.wind_mph)} mph`,
        rain:
          checkpoint.weather.rain_in_hr === null
            ? "n/a"
            : `${formatValue(checkpoint.weather.rain_in_hr, 2)} in/hr`,
        snow:
          checkpoint.weather.snow_in_hr === null
            ? "n/a"
            : `${formatValue(checkpoint.weather.snow_in_hr, 2)} in/hr`,
        risk: checkpoint.combined_risk ?? "unknown",
        risk_label: riskLabel(checkpoint.combined_risk),
        note: checkpoint.no_travel_reason ?? "",
      },
      geometry: {
        type: "Point",
        coordinates: [
          checkpoint.coordinate.longitude,
          checkpoint.coordinate.latitude,
        ],
      },
    })),
  };
}

export function RouteMap({
  routes,
  grid,
  heatDomain,
  showHeatmap,
  recommendedId,
  selectedRouteId,
  onSelectRoute,
  variable,
  forecastHour,
}: RouteMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const layersRef = useRef<string[]>([]);
  const selectRouteRef = useRef(onSelectRoute);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    selectRouteRef.current = onSelectRoute;
  }, [onSelectRoute]);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) {
      return;
    }
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: MAP_STYLE,
      center: [-107.5, 40.5],
      zoom: 5,
      attributionControl: { compact: true },
    });
    map.addControl(new NavigationControl({ showCompass: false }), "top-left");
    map.on("load", () => setReady(true));

    map.on("click", (event) => {
      const layers = layersRef.current;
      if (layers.length === 0) {
        return;
      }
      const features = map.queryRenderedFeatures(event.point, { layers });
      if (features.length === 0) {
        return;
      }
      const feature = features[0];
      const properties = feature.properties ?? {};
      if (feature.layer.id.startsWith("checkpoint-circle-")) {
        const level = properties.risk as RiskLevelName | "unknown";
        const color =
          level in RISK_META ? RISK_META[level as RiskLevelName].color : "#8a8f98";
        const note = properties.note
          ? `<p class="popup-note">${escapeHtml(properties.note)}</p>`
          : "";
        new Popup({ closeButton: true, maxWidth: "280px" })
          .setLngLat(event.lngLat)
          .setHTML(
            `<div class="popup">
              <strong>${escapeHtml(properties.route_label)} &middot; checkpoint ${escapeHtml(
                properties.sequence,
              )}</strong>
              <div>Mile ${escapeHtml(properties.mile)} &middot; ETA ${escapeHtml(
                properties.eta,
              )}</div>
              <div>Wind ${escapeHtml(properties.wind)} &middot; Rain ${escapeHtml(
                properties.rain,
              )} &middot; Snow ${escapeHtml(properties.snow)}</div>
              <div>Combined: <span style="color:${color};font-weight:600">${escapeHtml(
                properties.risk_label,
              )}</span></div>
              ${note}
            </div>`,
          )
          .addTo(map);
        if (typeof properties.route_id === "string") {
          selectRouteRef.current(properties.route_id);
        }
      } else if (feature.layer.id.startsWith("route-line-")) {
        if (typeof feature.properties?.route_id === "string") {
          selectRouteRef.current(feature.properties.route_id);
        }
      }
    });

    const handleResize = () => map.resize();
    window.addEventListener("resize", handleResize);
    mapRef.current = map;
    return () => {
      window.removeEventListener("resize", handleResize);
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) {
      return;
    }
    removeLayersAndSources(map, ROUTE_LAYER_PREFIXES);
    const managed: string[] = [];

    routes.forEach((route, index) => {
      const isSelected = route.id === selectedRouteId;
      const isRecommended = route.id === recommendedId;
      const color = routeColor(index);

      const lineSource = `route-line-${route.id}`;
      setSource(map, lineSource, buildRouteLine(route));
      map.addLayer({
        id: `route-line-${route.id}`,
        type: "line",
        source: lineSource,
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-color": color,
          "line-width": isSelected ? 6 : isRecommended ? 4.5 : 3,
          "line-opacity": isSelected ? 0.95 : 0.4,
        },
      });
      managed.push(`route-line-${route.id}`);

      setSource(map, `checkpoint-circle-${route.id}`, buildCheckpoints(route));
      map.addLayer({
        id: `checkpoint-circle-${route.id}`,
        type: "circle",
        source: `checkpoint-circle-${route.id}`,
        paint: {
          "circle-radius": isSelected ? 5.5 : 3.8,
          "circle-color": riskMatchExpression("#8a8f98") as never,
          "circle-stroke-color": "#ffffff",
          "circle-stroke-width": 1.4,
          "circle-opacity": isSelected ? 1 : 0.5,
        },
      });
      managed.push(`checkpoint-circle-${route.id}`);
    });

    if (routes.length > 0) {
      const first = routes[0].geometry[0];
      const lastRoute = routes[0].geometry[routes[0].geometry.length - 1];
      setSource(map, "endpoint-src", {
        type: "FeatureCollection",
        features: [
          {
            type: "Feature",
            properties: { kind: "origin" },
            geometry: { type: "Point", coordinates: first },
          },
          {
            type: "Feature",
            properties: { kind: "destination" },
            geometry: { type: "Point", coordinates: lastRoute },
          },
        ],
      });
      map.addLayer({
        id: "endpoint-circle",
        type: "circle",
        source: "endpoint-src",
        paint: {
          "circle-radius": 7,
          "circle-color": [
            "match",
            ["get", "kind"],
            "origin",
            "#111827",
            "#b91c1c",
          ],
          "circle-stroke-color": "#ffffff",
          "circle-stroke-width": 2,
        },
      });
      managed.push("endpoint-circle");
    }

    layersRef.current = managed;

    const bounds = routes.flatMap((route) =>
      route.geometry.map(([lon, lat]) => [lon, lat] as [number, number]),
    );
    if (bounds.length > 0) {
      const lngLatBounds = bounds.reduce(
        (acc, coordinate) => acc.extend(coordinate),
        new maplibregl.LngLatBounds(bounds[0], bounds[0]),
      );
      map.fitBounds(lngLatBounds, { padding: 70, duration: 700, maxZoom: 9 });
    }
  }, [ready, routes, selectedRouteId, recommendedId]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) {
      return;
    }

    const sourceId = `${HEAT_PREFIX}src`;
    const layerId = `${HEAT_PREFIX}fill`;
    const hasGrid = Boolean(grid && grid.points.length > 0);
    const data = hasGrid
      ? buildHeatCells(grid as HeatGrid, variable, forecastHour)
      : { type: "FeatureCollection", features: [] };

    const existing = map.getSource(sourceId) as GeoJSONSource | undefined;
    if (existing) {
      existing.setData(data as never);
    } else {
      map.addSource(sourceId, { type: "geojson", data: data as never });
    }

    const color = hasGrid
      ? heatColorExpression(heatDomain, VARIABLES[variable].gradient)
      : "#000000";
    const opacity = hasGrid && showHeatmap ? 0.6 : 0;

    if (map.getLayer(layerId)) {
      map.setPaintProperty(layerId, "fill-color", color as never);
      map.setPaintProperty(layerId, "fill-opacity", opacity);
    } else {
      map.addLayer(
        {
          id: layerId,
          type: "fill",
          source: sourceId,
          paint: {
            "fill-color": color as never,
            "fill-opacity": opacity,
            "fill-outline-color": "rgba(255, 255, 255, 0.25)",
          },
        },
        firstLayerId(map, ROUTE_LAYER_PREFIXES),
      );
    }
  }, [ready, grid, variable, forecastHour, heatDomain, showHeatmap, routes]);

  return <div ref={containerRef} className="map-canvas" />;
}
