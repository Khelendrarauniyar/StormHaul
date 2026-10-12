from __future__ import annotations

import math
from typing import List, Sequence, Tuple

EARTH_RADIUS_MILES = 3958.7613


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2.0) ** 2
    )
    return 2.0 * EARTH_RADIUS_MILES * math.asin(min(1.0, math.sqrt(a)))


def cumulative_miles(coordinates: Sequence[Sequence[float]]) -> List[float]:
    cumulative = [0.0]
    for index in range(1, len(coordinates)):
        lon1, lat1 = coordinates[index - 1]
        lon2, lat2 = coordinates[index]
        cumulative.append(
            cumulative[-1] + haversine_miles(lat1, lon1, lat2, lon2)
        )
    return cumulative


def interpolate(
    coordinates: Sequence[Sequence[float]],
    cumulative: Sequence[float],
    target_miles: float,
) -> Tuple[float, float]:
    if not coordinates:
        raise ValueError("Cannot interpolate an empty geometry.")
    if target_miles <= 0.0:
        lon, lat = coordinates[0]
        return lat, lon
    if target_miles >= cumulative[-1]:
        lon, lat = coordinates[-1]
        return lat, lon

    low = 0
    high = len(cumulative) - 1
    while low < high - 1:
        mid = (low + high) // 2
        if cumulative[mid] <= target_miles:
            low = mid
        else:
            high = mid

    span = cumulative[high] - cumulative[low]
    ratio = 0.0 if span <= 0.0 else (target_miles - cumulative[low]) / span
    lon1, lat1 = coordinates[low]
    lon2, lat2 = coordinates[high]
    return lat1 + (lat2 - lat1) * ratio, lon1 + (lon2 - lon1) * ratio


def sample_along_route(
    coordinates: Sequence[Sequence[float]],
    interval_miles: float,
    max_points: int = 40,
) -> List[Tuple[float, float, float]]:
    if not coordinates:
        return []
    cumulative = cumulative_miles(coordinates)
    total = cumulative[-1]
    if total <= 0.0:
        lon, lat = coordinates[0]
        return [(lat, lon, 0.0)]

    effective_interval = max(interval_miles, total / max_points)
    targets: List[float] = []
    distance = 0.0
    while distance < total - 1e-6:
        targets.append(distance)
        distance += effective_interval
    targets.append(total)

    samples: List[Tuple[float, float, float]] = []
    for target in targets:
        lat, lon = interpolate(coordinates, cumulative, target)
        samples.append((lat, lon, target))
    return samples


def _perpendicular_distance(
    point: Sequence[float], start: Sequence[float], end: Sequence[float]
) -> float:
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    if dx == 0.0 and dy == 0.0:
        return math.hypot(point[0] - start[0], point[1] - start[1])
    t = ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    proj_lon = start[0] + t * dx
    proj_lat = start[1] + t * dy
    return math.hypot(point[0] - proj_lon, point[1] - proj_lat)


def simplify_line(
    coordinates: Sequence[Sequence[float]], epsilon: float
) -> List[List[float]]:
    points = [list(point) for point in coordinates]
    if epsilon <= 0.0 or len(points) < 3:
        return points

    keep = [False] * len(points)
    keep[0] = True
    keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        first, last = stack.pop()
        if last <= first + 1:
            continue
        start, end = points[first], points[last]
        furthest = -1.0
        index = -1
        for cursor in range(first + 1, last):
            distance = _perpendicular_distance(points[cursor], start, end)
            if distance > furthest:
                furthest = distance
                index = cursor
        if furthest > epsilon:
            keep[index] = True
            stack.append((first, index))
            stack.append((index, last))

    return [point for point, flag in zip(points, keep) if flag]
