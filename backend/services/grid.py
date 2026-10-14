from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence, Tuple

GRID_MAX_POINTS = 120
GRID_MIN_DIM = 6
GRID_PAD_FRACTION = 0.15
GRID_PAD_MIN_DEGREES = 0.2
MIN_SPAN = 1e-3

Bounds = Tuple[float, float, float, float]


def route_bounds(coordinates: Sequence[Sequence[float]]) -> Optional[Bounds]:
    if not coordinates:
        return None
    latitudes = [point[1] for point in coordinates]
    longitudes = [point[0] for point in coordinates]
    return (min(latitudes), max(latitudes), min(longitudes), max(longitudes))


def union_bounds(bounds_list: Sequence[Optional[Bounds]]) -> Optional[Bounds]:
    present = [bounds for bounds in bounds_list if bounds is not None]
    if not present:
        return None
    return (
        min(bounds[0] for bounds in present),
        max(bounds[1] for bounds in present),
        min(bounds[2] for bounds in present),
        max(bounds[3] for bounds in present),
    )


def padded_bounds(bounds: Bounds) -> Bounds:
    south, north, west, east = bounds
    span_lat = max(north - south, MIN_SPAN)
    span_lon = max(east - west, MIN_SPAN)
    pad_lat = max(GRID_PAD_MIN_DEGREES, span_lat * GRID_PAD_FRACTION)
    pad_lon = max(GRID_PAD_MIN_DEGREES, span_lon * GRID_PAD_FRACTION)
    return (south - pad_lat, north + pad_lat, west - pad_lon, east + pad_lon)


def grid_dimensions(bounds: Bounds, max_points: int = GRID_MAX_POINTS) -> Tuple[int, int]:
    south, north, west, east = bounds
    span_lat = max(north - south, MIN_SPAN)
    span_lon = max(east - west, MIN_SPAN)
    mid_latitude = (south + north) / 2.0
    lon_scale = max(0.2, math.cos(math.radians(mid_latitude)))
    aspect = (span_lon * lon_scale) / span_lat
    columns = max(GRID_MIN_DIM, int(round(math.sqrt(max_points * aspect))))
    rows = max(GRID_MIN_DIM, int(round(max_points / columns)))
    while rows * columns > max_points:
        if rows >= columns:
            rows -= 1
        else:
            columns -= 1
    return rows, columns


def grid_points(
    bounds: Bounds, rows: int, columns: int
) -> Tuple[List[Tuple[float, float]], float, float]:
    south, north, west, east = bounds
    latitude_step = (north - south) / rows
    longitude_step = (east - west) / columns
    latitudes = [south + latitude_step * (index + 0.5) for index in range(rows)]
    longitudes = [west + longitude_step * (index + 0.5) for index in range(columns)]
    points = [(latitude, longitude) for latitude in latitudes for longitude in longitudes]
    return points, latitude_step, longitude_step


def build_grid(bounds: Bounds, max_points: int = GRID_MAX_POINTS) -> Dict[str, object]:
    padded = padded_bounds(bounds)
    rows, columns = grid_dimensions(padded, max_points)
    points, latitude_step, longitude_step = grid_points(padded, rows, columns)
    return {
        "bounds": {
            "south": padded[0],
            "north": padded[1],
            "west": padded[2],
            "east": padded[3],
        },
        "rows": rows,
        "columns": columns,
        "spacing_latitude": latitude_step,
        "spacing_longitude": longitude_step,
        "points": points,
    }
