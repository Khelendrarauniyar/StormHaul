from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional


class RiskLevel(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    SEVERE = "severe"
    NO_TRAVEL = "no_travel"


RISK_ORDER = {
    RiskLevel.LOW: 0,
    RiskLevel.MODERATE: 1,
    RiskLevel.HIGH: 2,
    RiskLevel.SEVERE: 3,
    RiskLevel.NO_TRAVEL: 4,
}

RISK_NUMERIC = {level.value: float(rank) for level, rank in RISK_ORDER.items()}


def most_severe(*levels: Optional[RiskLevel]) -> Optional[RiskLevel]:
    present = [level for level in levels if level is not None]
    if not present:
        return None
    return max(present, key=lambda level: RISK_ORDER[level])


@dataclass
class GeoPlace:
    query: str
    label: str
    latitude: float
    longitude: float
    source: str


@dataclass
class RouteGeometry:
    label: str
    coordinates: List[List[float]]
    distance_miles: float
    duration_seconds: float
    source: str


@dataclass
class WeatherSample:
    wind_mph: Optional[float]
    rain_in_hr: Optional[float]
    snow_in_hr: Optional[float]
    temperature_c: Optional[float]
    observed_at: Optional[datetime]
    available: bool
    source: str


@dataclass
class Checkpoint:
    sequence: int
    latitude: float
    longitude: float
    cumulative_miles: float
    arrival_at: datetime
    distance_from_previous_miles: float = 0.0
    weather: Optional[WeatherSample] = None
    wind_level: Optional[RiskLevel] = None
    rain_level: Optional[RiskLevel] = None
    snow_level: Optional[RiskLevel] = None
    combined_risk: Optional[RiskLevel] = None
    no_travel_reason: Optional[str] = None


@dataclass
class RouteRiskSummary:
    low_miles: float = 0.0
    moderate_miles: float = 0.0
    high_miles: float = 0.0
    severe_miles: float = 0.0
    no_travel_miles: float = 0.0
    unknown_miles: float = 0.0
    average_risk: float = 0.0
    total_miles: float = 0.0


@dataclass
class RouteResult:
    id: str
    label: str
    source: str
    coordinates: List[List[float]]
    distance_miles: float
    duration_seconds: float
    arrival_at: datetime
    feasible: bool = True
    checkpoints: List[Checkpoint] = field(default_factory=list)
    risk_summary: RouteRiskSummary = field(default_factory=RouteRiskSummary)
