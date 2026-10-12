from __future__ import annotations

import logging
import math
import os
import re
import time
from typing import List, Sequence, Tuple

import requests

from .exceptions import GeocodingError, GeocodingNotFound, RoutingProviderError
from .geo import simplify_line
from .models import GeoPlace, RouteGeometry

logger = logging.getLogger(__name__)

METERS_PER_MILE = 1609.344
DEFAULT_TIMEOUT = float(os.getenv("PROVIDER_TIMEOUT_SECONDS", "12"))
GEOCODING_ATTEMPTS = 3
AVERAGE_DEMO_SPEED_MPH = 55.0
COORDINATE_PRECISION = 5
SIMPLIFY_EPSILON_DEGREES = 0.0005

_COORDINATE_PATTERN = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$")


def _base_url(name: str, default: str) -> str:
    return os.getenv(name, default).rstrip("/")


def _clean_coordinates(coordinates: Sequence[Sequence[float]]) -> List[List[float]]:
    simplified = simplify_line(coordinates, SIMPLIFY_EPSILON_DEGREES)
    return [
        [round(point[0], COORDINATE_PRECISION), round(point[1], COORDINATE_PRECISION)]
        for point in simplified
    ]


def _place_label(item: dict) -> str:
    return ", ".join(
        part for part in (item.get("name"), item.get("admin1"), item.get("country")) if part
    )


def _place_from_item(item: dict, query: str) -> GeoPlace:
    return GeoPlace(
        query=query,
        label=_place_label(item) or query,
        latitude=float(item["latitude"]),
        longitude=float(item["longitude"]),
        source="open-meteo-geocoding",
    )


def _geocoding_search(query: str, count: int) -> List[dict]:
    base = _base_url("GEOCODING_BASE_URL", "https://geocoding-api.open-meteo.com")
    params = {"name": query, "count": count, "language": "en", "format": "json"}
    payload = None
    last_error: Exception | None = None
    for attempt in range(GEOCODING_ATTEMPTS):
        try:
            response = requests.get(
                f"{base}/v1/search", params=params, timeout=DEFAULT_TIMEOUT
            )
            response.raise_for_status()
            payload = response.json()
            break
        except ValueError as exc:
            raise GeocodingError("The geocoding provider returned malformed JSON.") from exc
        except requests.RequestException as exc:
            last_error = exc
            if attempt < GEOCODING_ATTEMPTS - 1:
                time.sleep(0.4 * (attempt + 1))
                continue
            logger.warning("Geocoding request failed: %s", exc)
            raise GeocodingError("The geocoding provider is unavailable.") from exc

    if payload is None:
        logger.warning("Geocoding request failed: %s", last_error)
        raise GeocodingError("The geocoding provider is unavailable.")
    return payload.get("results") or []


def search_places(query: str, count: int = 6) -> List[GeoPlace]:
    query = (query or "").strip()
    if len(query) < 2:
        return []
    return [_place_from_item(item, query) for item in _geocoding_search(query, count)]


def geocode(query: str) -> GeoPlace:
    query = (query or "").strip()
    literal = _COORDINATE_PATTERN.match(query)
    if literal:
        latitude = float(literal.group(1))
        longitude = float(literal.group(2))
        if -90.0 <= latitude <= 90.0 and -180.0 <= longitude <= 180.0:
            return GeoPlace(
                query=query,
                label=f"{latitude:.4f}, {longitude:.4f}",
                latitude=latitude,
                longitude=longitude,
                source="literal-coordinates",
            )

    results = _geocoding_search(query, 1)
    if not results:
        raise GeocodingNotFound(f"Could not find a location for '{query}'.")
    return _place_from_item(results[0], query)


def get_alternatives(
    origin: GeoPlace, destination: GeoPlace
) -> Tuple[List[RouteGeometry], str, List[str]]:
    warnings: List[str] = []
    routes: List[RouteGeometry] = []

    if os.getenv("ORS_API_KEY"):
        try:
            routes = _ors_directions(origin, destination, alternatives=True)
        except RoutingProviderError:
            try:
                routes = [_ors_directions(origin, destination, alternatives=False)[0]]
            except (RoutingProviderError, IndexError):
                warnings.append(
                    "OpenRouteService was unavailable; using the OSRM demo server."
                )
                routes = []

    if len(routes) < 3:
        try:
            osrm_routes = _osrm_alternatives(origin, destination, warnings)
        except RoutingProviderError:
            osrm_routes = []
            warnings.append("The OSRM demo server was unreachable.")
        for candidate in osrm_routes:
            if len(routes) >= 3:
                break
            if _is_distinct(candidate, routes):
                routes.append(candidate)

    if len(routes) >= 1:
        for index, route in enumerate(routes[:3]):
            route.label = f"Route {chr(65 + index)}"
        return routes[:3], _routing_source(routes[:3]), warnings

    warnings.append(
        "Routing providers were unreachable, so clearly labelled synthetic demo "
        "routes were generated. Weather is still real."
    )
    return _synthetic_routes(origin, destination), "synthetic-demo", warnings


def _routing_source(routes: Sequence[RouteGeometry]) -> str:
    seen: List[str] = []
    for route in routes:
        if route.source not in seen:
            seen.append(route.source)
    return "+".join(seen) if seen else "unknown"


def _ors_directions(
    origin: GeoPlace, destination: GeoPlace, alternatives: bool
) -> List[RouteGeometry]:
    base = _base_url("ORS_BASE_URL", "https://api.openrouteservice.org")
    body: dict = {
        "coordinates": [
            [origin.longitude, origin.latitude],
            [destination.longitude, destination.latitude],
        ],
        "units": "mi",
    }
    if alternatives:
        body["alternative_routes"] = {
            "target_count": 3,
            "weight_factor": 1.6,
            "share_factor": 0.6,
        }
    headers = {
        "Authorization": os.getenv("ORS_API_KEY", ""),
        "Content-Type": "application/json",
    }
    try:
        response = requests.post(
            f"{base}/v2/directions/driving-hgv/geojson",
            json=body,
            headers=headers,
            timeout=DEFAULT_TIMEOUT,
        )
    except requests.RequestException as exc:
        logger.warning("OpenRouteService request failed: %s", exc)
        raise RoutingProviderError("OpenRouteService is unavailable.") from exc

    if response.status_code != 200:
        logger.warning("OpenRouteService returned HTTP %s", response.status_code)
        raise RoutingProviderError(
            f"OpenRouteService returned HTTP {response.status_code}."
        )
    try:
        payload = response.json()
    except ValueError as exc:
        raise RoutingProviderError("OpenRouteService returned malformed JSON.") from exc

    routes: List[RouteGeometry] = []
    for index, feature in enumerate(payload.get("features", [])):
        summary = feature.get("properties", {}).get("summary", {})
        geometry = feature.get("geometry", {}).get("coordinates", [])
        if not geometry or "distance" not in summary:
            continue
        routes.append(
            RouteGeometry(
                label=f"Route {chr(65 + index)}",
                coordinates=_clean_coordinates(geometry),
                distance_miles=float(summary["distance"]),
                duration_seconds=float(summary["duration"]),
                source="openrouteservice",
            )
        )
    if not routes:
        raise RoutingProviderError("no usable route in response")
    return routes


def _osrm_request(coordinates: Sequence[Sequence[float]], alternatives: bool):
    base = _base_url("OSRM_BASE_URL", "https://router.project-osrm.org")
    path = ";".join(f"{lon},{lat}" for lon, lat in coordinates)
    params = {
        "overview": "full",
        "geometries": "geojson",
        "steps": "false",
        "alternatives": "true" if alternatives else "false",
    }
    try:
        response = requests.get(
            f"{base}/route/v1/driving/{path}", params=params, timeout=DEFAULT_TIMEOUT
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        logger.warning("OSRM request failed: %s", exc)
        raise RoutingProviderError("The OSRM demo server is unavailable.") from exc
    except ValueError as exc:
        raise RoutingProviderError("The OSRM demo server returned malformed JSON.") from exc


def _parse_osrm_routes(payload) -> List[RouteGeometry]:
    routes: List[RouteGeometry] = []
    for index, route in enumerate(payload.get("routes", [])):
        geometry = route.get("geometry", {}).get("coordinates", [])
        if not geometry:
            continue
        routes.append(
            RouteGeometry(
                label=f"Route {chr(65 + index)}",
                coordinates=_clean_coordinates(geometry),
                distance_miles=float(route["distance"]) / METERS_PER_MILE,
                duration_seconds=float(route["duration"]),
                source="osrm-demo",
            )
        )
    return routes


def _osrm_alternatives(
    origin: GeoPlace, destination: GeoPlace, warnings: List[str]
) -> List[RouteGeometry]:
    start = (origin.longitude, origin.latitude)
    end = (destination.longitude, destination.latitude)
    routes = _parse_osrm_routes(_osrm_request([start, end], alternatives=True))

    if len(routes) < 3:
        for sign in (1.0, -1.0):
            if len(routes) >= 3:
                break
            via = _offset_midpoint(start, end, sign, 0.18)
            try:
                extra = _parse_osrm_routes(
                    _osrm_request([start, via, end], alternatives=False)
                )
            except RoutingProviderError:
                extra = []
            for candidate in extra:
                if _is_distinct(candidate, routes):
                    candidate.label = f"Route {chr(65 + len(routes))}"
                    routes.append(candidate)
                    break

    if not routes:
        raise RoutingProviderError("OSRM returned no usable routes.")
    return routes


def _offset_midpoint(
    start: Sequence[float], end: Sequence[float], sign: float, fraction: float
) -> Tuple[float, float]:
    mid_lon = (start[0] + end[0]) / 2.0
    mid_lat = (start[1] + end[1]) / 2.0
    d_lon = end[0] - start[0]
    d_lat = end[1] - start[1]
    magnitude = math.hypot(d_lon, d_lat) or 1.0
    perp_lon = -d_lat / magnitude
    perp_lat = d_lon / magnitude
    return (
        mid_lon + sign * perp_lon * fraction * magnitude,
        mid_lat + sign * perp_lat * fraction * magnitude,
    )


def _is_distinct(candidate: RouteGeometry, existing: Sequence[RouteGeometry]) -> bool:
    for route in existing:
        if abs(candidate.distance_miles - route.distance_miles) < 1.0:
            return False
    return True


def _synthetic_routes(
    origin: GeoPlace, destination: GeoPlace
) -> List[RouteGeometry]:
    a = (origin.longitude, origin.latitude)
    b = (destination.longitude, destination.latitude)
    variants = ((0.0, "Route A"), (0.12, "Route B"), (-0.12, "Route C"))
    routes: List[RouteGeometry] = []
    for bulge, label in variants:
        coordinates = _clean_coordinates(_bulged_line(a, b, bulge, points=64))
        distance = _polyline_miles(coordinates)
        duration = (distance / AVERAGE_DEMO_SPEED_MPH) * 3600.0
        routes.append(
            RouteGeometry(
                label=label,
                coordinates=coordinates,
                distance_miles=distance,
                duration_seconds=duration,
                source="synthetic-demo",
            )
        )
    return routes


def _bulged_line(
    start: Sequence[float], end: Sequence[float], bulge: float, points: int
) -> List[List[float]]:
    d_lon = end[0] - start[0]
    d_lat = end[1] - start[1]
    magnitude = math.hypot(d_lon, d_lat) or 1.0
    perp_lon = -d_lat / magnitude
    perp_lat = d_lon / magnitude
    coordinates: List[List[float]] = []
    for index in range(points + 1):
        t = index / points
        lon = start[0] + d_lon * t + perp_lon * bulge * magnitude * math.sin(math.pi * t)
        lat = start[1] + d_lat * t + perp_lat * bulge * magnitude * math.sin(math.pi * t)
        coordinates.append([lon, lat])
    return coordinates


def _polyline_miles(coordinates: Sequence[Sequence[float]]) -> float:
    from .geo import cumulative_miles

    return cumulative_miles(coordinates)[-1]
