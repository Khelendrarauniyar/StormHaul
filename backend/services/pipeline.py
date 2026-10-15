from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from .checkpoints import build_checkpoints
from .exceptions import WeatherProviderError
from .grid import build_grid, route_bounds, union_bounds
from .models import (
    Checkpoint,
    GeoPlace,
    RouteResult,
    WeatherSample,
)
from .recommendation import recommend
from .risk import assess_checkpoint_weather, summarize_route
from .routing_provider import geocode, get_alternatives
from .weather_provider import align_series, floor_to_hour, value_at
from .weather_service import build_weather_service

logger = logging.getLogger(__name__)

FORECAST_HOURS = 48

ASSUMPTIONS = [
    "Boundary values are assigned to the more hazardous category; the only "
    "exception is the top no-travel band for rain (>1.00 in/hr) and snow "
    "(>3.0 in/hr), which the brief specifies as strictly greater.",
    "Checkpoint arrival times are interpolated proportionally to cumulative "
    "distance along the route geometry, which is an approximation of provider "
    "step durations.",
    "Combined checkpoint risk is the most severe single hazard at that "
    "checkpoint; No Travel is a separate hard-stop status.",
    "Risk mileage uses the distance each checkpoint represents (neighbour "
    "midpoints), not an equal share per checkpoint.",
    "Average risk is the distance-weighted mean of Low=0, Moderate=1, High=2, "
    "Severe=3, No Travel=4. This numeric mapping is an implementation choice.",
    "A route is marked infeasible when any No Travel segment is present; feasible "
    "routes always rank above infeasible ones.",
    "Weather is sampled at the hour bucket containing the estimated arrival time.",
    "The heat map is a regular latitude/longitude grid sampled around the planned "
    "routes; each cell reports the forecast at its centre, so the field is coarser "
    "than a numerical weather model.",
    "Units: distance in miles, wind in mph (sustained), rain and snow in inches per hour.",
]


def build_route_plan(params: dict) -> dict:
    request_id = uuid.uuid4().hex
    warnings: List[str] = []

    departure = params["departure_at"]
    if departure.tzinfo is None:
        departure = departure.replace(tzinfo=timezone.utc)
    departure = departure.astimezone(timezone.utc)
    load_weight_lb = params["load_weight_lb"]
    interval_miles = params["checkpoint_interval_miles"]

    origin = _resolve_place(
        params["origin"], params.get("origin_latitude"), params.get("origin_longitude")
    )
    destination = _resolve_place(
        params["destination"],
        params.get("destination_latitude"),
        params.get("destination_longitude"),
    )

    routes, routing_source, routing_warnings = get_alternatives(origin, destination)
    warnings.extend(routing_warnings)

    route_results: List[RouteResult] = []
    for index, geometry in enumerate(routes):
        checkpoints = build_checkpoints(
            geometry.coordinates,
            geometry.distance_miles,
            geometry.duration_seconds,
            departure,
            interval_miles,
        )
        route_results.append(
            RouteResult(
                id=f"route-{index + 1}",
                label=geometry.label,
                source=geometry.source,
                coordinates=geometry.coordinates,
                distance_miles=round(geometry.distance_miles, 3),
                duration_seconds=round(geometry.duration_seconds, 1),
                arrival_at=departure + timedelta(seconds=geometry.duration_seconds),
                checkpoints=checkpoints,
            )
        )

    grid_bounds = union_bounds([route_bounds(route.coordinates) for route in route_results])
    grid_spec = build_grid(grid_bounds) if grid_bounds else None

    forecast_start = floor_to_hour(departure)
    weather_client = build_weather_service()
    weather_available = True
    sources: List[str] = []
    try:
        weather_points = [
            (checkpoint.latitude, checkpoint.longitude)
            for route in route_results
            for checkpoint in route.checkpoints
        ]
        if grid_spec:
            weather_points.extend(grid_spec["points"])
        weather_client.fetch(weather_points)
        sources = weather_client.sources
    except WeatherProviderError as exc:
        logger.warning("Weather provider unavailable: %s", exc)
        weather_available = False
        warnings.append(
            "The weather provider was unavailable; checkpoints are returned without "
            "forecast values and risk mileage excludes them."
        )

    for route in route_results:
        for checkpoint in route.checkpoints:
            series = (
                weather_client.get(checkpoint.latitude, checkpoint.longitude)
                if weather_available
                else None
            )
            source = (
                weather_client.source_for(checkpoint.latitude, checkpoint.longitude)
                if weather_available
                else None
            )
            checkpoint.weather = _build_sample(
                series, checkpoint.arrival_at, weather_available, source
            )
            assessment = assess_checkpoint_weather(checkpoint.weather, load_weight_lb)
            checkpoint.wind_level = assessment.wind
            checkpoint.rain_level = assessment.rain
            checkpoint.snow_level = assessment.snow
            checkpoint.combined_risk = assessment.combined
            checkpoint.no_travel_reason = assessment.no_travel_reason
        route.risk_summary = summarize_route(route.checkpoints, route.distance_miles)
        route.feasible = route.risk_summary.no_travel_miles <= 0.0

    recommended, reasons = recommend(route_results)

    grid = _build_grid(grid_spec, weather_client, forecast_start, weather_available)

    warnings.extend(_coverage_warnings(route_results))

    return {
        "request_id": request_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "units": {
            "distance": "miles",
            "wind": "mph",
            "rain": "in/hr",
            "snow": "in/hr",
            "load": "lb",
        },
        "data_sources": {
            "geocoding": origin.source if origin.source == destination.source else "mixed",
            "routing": routing_source,
            "weather": ",".join(sources) if weather_available and sources else "unavailable",
        },
        "origin": _place_payload(origin),
        "destination": _place_payload(destination),
        "departure_at": departure.isoformat(),
        "checkpoint_interval_miles": interval_miles,
        "load_weight_lb": load_weight_lb,
        "forecast_coverage": {
            "start": forecast_start.isoformat(),
            "end": (forecast_start + timedelta(hours=FORECAST_HOURS)).isoformat(),
            "hours": FORECAST_HOURS,
        },
        "forecast_times": [
            (forecast_start + timedelta(hours=offset)).isoformat()
            for offset in range(FORECAST_HOURS)
        ],
        "grid": grid,
        "routes": [_route_payload(route) for route in route_results],
        "recommended_route_id": recommended.id,
        "recommendation_reasons": reasons,
        "assumptions": ASSUMPTIONS,
        "warnings": warnings,
        "weather_available": weather_available,
    }


def _resolve_place(
    text: str, latitude: Optional[float], longitude: Optional[float]
) -> GeoPlace:
    if latitude is not None and longitude is not None:
        return GeoPlace(
            query=text,
            label=text,
            latitude=latitude,
            longitude=longitude,
            source="selected",
        )
    return geocode(text)


def _place_payload(place: GeoPlace) -> dict:
    return {
        "query": place.query,
        "label": place.label,
        "latitude": round(place.latitude, 6),
        "longitude": round(place.longitude, 6),
        "source": place.source,
    }


def _build_sample(
    series: Optional[Dict[str, list]],
    arrival: datetime,
    weather_available: bool,
    source: Optional[str],
) -> WeatherSample:
    if not weather_available or not series:
        return WeatherSample(
            wind_mph=None,
            rain_in_hr=None,
            snow_in_hr=None,
            temperature_c=None,
            observed_at=None,
            available=False,
            source="unavailable",
        )
    observed_at = floor_to_hour(arrival)
    return WeatherSample(
        wind_mph=value_at(series, "wind_mph", arrival),
        rain_in_hr=value_at(series, "rain_in_hr", arrival),
        snow_in_hr=value_at(series, "snow_in_hr", arrival),
        temperature_c=value_at(series, "temperature_c", arrival),
        observed_at=observed_at,
        available=True,
        source=source or "unavailable",
    )


def _build_grid(
    spec: Optional[dict],
    client,
    forecast_start: datetime,
    weather_available: bool,
) -> dict:
    if not spec:
        return {
            "bounds": None,
            "rows": 0,
            "columns": 0,
            "spacing_latitude": 0.0,
            "spacing_longitude": 0.0,
            "points": [],
        }

    meta = {
        "bounds": {
            key: round(value, 6) for key, value in spec["bounds"].items()
        },
        "rows": spec["rows"],
        "columns": spec["columns"],
        "spacing_latitude": round(spec["spacing_latitude"], 6),
        "spacing_longitude": round(spec["spacing_longitude"], 6),
    }

    if not weather_available:
        return {**meta, "points": []}

    points: List[dict] = []
    for latitude, longitude in spec["points"]:
        series = client.get(latitude, longitude)
        wind, rain, snow = align_series(series, forecast_start, FORECAST_HOURS)
        points.append(
            {
                "latitude": round(latitude, 5),
                "longitude": round(longitude, 5),
                "wind_mph": [None if v is None else round(v, 2) for v in wind],
                "rain_in_hr": [None if v is None else round(v, 4) for v in rain],
                "snow_in_hr": [None if v is None else round(v, 4) for v in snow],
            }
        )
    return {**meta, "points": points}


def _route_payload(route: RouteResult) -> dict:
    summary = route.risk_summary
    return {
        "id": route.id,
        "label": route.label,
        "source": route.source,
        "geometry": route.coordinates,
        "distance_miles": route.distance_miles,
        "duration_seconds": route.duration_seconds,
        "arrival_at": route.arrival_at.isoformat(),
        "feasible": route.feasible,
        "risk_summary": {
            "low_miles": summary.low_miles,
            "moderate_miles": summary.moderate_miles,
            "high_miles": summary.high_miles,
            "severe_miles": summary.severe_miles,
            "no_travel_miles": summary.no_travel_miles,
            "unknown_miles": summary.unknown_miles,
            "average_risk": summary.average_risk,
            "total_miles": summary.total_miles,
        },
        "checkpoints": [_checkpoint_payload(checkpoint) for checkpoint in route.checkpoints],
    }


def _checkpoint_payload(checkpoint: Checkpoint) -> dict:
    weather = checkpoint.weather
    return {
        "sequence": checkpoint.sequence,
        "coordinate": {
            "latitude": round(checkpoint.latitude, 6),
            "longitude": round(checkpoint.longitude, 6),
        },
        "cumulative_miles": round(checkpoint.cumulative_miles, 3),
        "distance_from_previous_miles": round(checkpoint.distance_from_previous_miles, 3),
        "arrival_at": checkpoint.arrival_at.isoformat(),
        "weather": {
            "available": bool(weather and weather.available),
            "wind_mph": None if not weather else weather.wind_mph,
            "rain_in_hr": None if not weather else weather.rain_in_hr,
            "snow_in_hr": None if not weather else weather.snow_in_hr,
            "temperature_c": None if not weather else weather.temperature_c,
            "observed_at": (
                None
                if not weather or weather.observed_at is None
                else weather.observed_at.isoformat()
            ),
            "source": "unavailable" if not weather else weather.source,
        },
        "hazards": {
            "wind": None if checkpoint.wind_level is None else checkpoint.wind_level.value,
            "rain": None if checkpoint.rain_level is None else checkpoint.rain_level.value,
            "snow": None if checkpoint.snow_level is None else checkpoint.snow_level.value,
        },
        "combined_risk": (
            None if checkpoint.combined_risk is None else checkpoint.combined_risk.value
        ),
        "no_travel_reason": checkpoint.no_travel_reason,
    }


def _coverage_warnings(route_results: List[RouteResult]) -> List[str]:
    warnings: List[str] = []
    for route in route_results:
        if route.risk_summary.unknown_miles > 0.0:
            warnings.append(
                f"{route.label} has {route.risk_summary.unknown_miles:,.1f} mi without "
                "forecast coverage; those miles are excluded from its risk totals."
            )
    return warnings
