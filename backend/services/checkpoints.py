from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Sequence

from .geo import cumulative_miles, interpolate
from .models import Checkpoint

DISTANCE_EPSILON_MILES = 1e-6


def checkpoint_targets(total_miles: float, interval_miles: float) -> List[float]:
    if total_miles <= 0.0:
        return [0.0]
    targets: List[float] = []
    distance = 0.0
    while distance < total_miles - DISTANCE_EPSILON_MILES:
        targets.append(distance)
        distance += interval_miles
    targets.append(total_miles)
    return targets


def build_checkpoints(
    coordinates: Sequence[Sequence[float]],
    distance_miles: float,
    duration_seconds: float,
    departure_at: datetime,
    interval_miles: float,
) -> List[Checkpoint]:
    geometric = cumulative_miles(coordinates)
    geometric_total = geometric[-1] if geometric else 0.0
    scale = (distance_miles / geometric_total) if geometric_total > 0.0 else 0.0
    scaled = [value * scale for value in geometric]

    checkpoints: List[Checkpoint] = []
    previous_distance = 0.0
    for sequence, target in enumerate(checkpoint_targets(distance_miles, interval_miles)):
        lat, lon = interpolate(coordinates, scaled, target)
        fraction = 0.0 if distance_miles <= 0.0 else min(
            1.0, max(0.0, target / distance_miles)
        )
        arrival = departure_at + timedelta(seconds=duration_seconds * fraction)
        checkpoints.append(
            Checkpoint(
                sequence=sequence,
                latitude=lat,
                longitude=lon,
                cumulative_miles=target,
                arrival_at=arrival,
                distance_from_previous_miles=target - previous_distance,
            )
        )
        previous_distance = target
    return checkpoints
