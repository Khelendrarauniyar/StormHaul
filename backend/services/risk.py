from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from .models import (
    Checkpoint,
    RISK_NUMERIC,
    RiskLevel,
    RouteRiskSummary,
    WeatherSample,
    most_severe,
)

WIND_THRESHOLDS: Tuple[Tuple[float, RiskLevel], ...] = (
    (25.0, RiskLevel.MODERATE),
    (35.0, RiskLevel.HIGH),
    (45.0, RiskLevel.SEVERE),
    (55.0, RiskLevel.NO_TRAVEL),
)
RAIN_THRESHOLDS: Tuple[Tuple[float, RiskLevel], ...] = (
    (0.10, RiskLevel.MODERATE),
    (0.25, RiskLevel.HIGH),
    (0.50, RiskLevel.SEVERE),
)
SNOW_THRESHOLDS: Tuple[Tuple[float, RiskLevel], ...] = (
    (0.5, RiskLevel.MODERATE),
    (1.0, RiskLevel.HIGH),
    (2.0, RiskLevel.SEVERE),
)

RAIN_NO_TRAVEL_IN_HR = 1.00
SNOW_NO_TRAVEL_IN_HR = 3.0

WIND_NO_TRAVEL_ANY_MPH = 55.0
WIND_NO_TRAVEL_LOAD_LB = 30_000
WIND_SEVERE_LOAD_LB = 40_000
WIND_NO_TRAVEL_BAND_MIN_MPH = 45.0
WIND_SEVERE_BAND_MIN_MPH = 35.0


@dataclass
class HazardAssessment:
    wind: Optional[RiskLevel]
    rain: Optional[RiskLevel]
    snow: Optional[RiskLevel]
    combined: Optional[RiskLevel]
    no_travel_reason: Optional[str]


def _classify(value: float, thresholds: Sequence[Tuple[float, RiskLevel]]) -> RiskLevel:
    level = RiskLevel.LOW
    for threshold, candidate in thresholds:
        if value >= threshold:
            level = candidate
    return level


def classify_wind(wind_mph: float) -> RiskLevel:
    return _classify(wind_mph, WIND_THRESHOLDS)


def classify_rain(rain_in_hr: float) -> RiskLevel:
    if rain_in_hr > RAIN_NO_TRAVEL_IN_HR:
        return RiskLevel.NO_TRAVEL
    return _classify(rain_in_hr, RAIN_THRESHOLDS)


def classify_snow(snow_in_hr: float) -> RiskLevel:
    if snow_in_hr > SNOW_NO_TRAVEL_IN_HR:
        return RiskLevel.NO_TRAVEL
    return _classify(snow_in_hr, SNOW_THRESHOLDS)


def assess_wind(
    wind_mph: float, load_weight_lb: float
) -> Tuple[RiskLevel, Optional[str]]:
    level = classify_wind(wind_mph)
    if wind_mph >= WIND_NO_TRAVEL_ANY_MPH:
        return level, (
            f"Wind {wind_mph:.1f} mph meets the >=55 mph no-travel rule for any load."
        )
    if (
        WIND_NO_TRAVEL_BAND_MIN_MPH <= wind_mph < WIND_NO_TRAVEL_ANY_MPH
        and load_weight_lb > WIND_NO_TRAVEL_LOAD_LB
    ):
        return RiskLevel.NO_TRAVEL, (
            f"Wind {wind_mph:.1f} mph with a {load_weight_lb:,} lb load triggers the "
            "45-54 mph / over 30,000 lb no-travel rule."
        )
    if (
        WIND_SEVERE_BAND_MIN_MPH <= wind_mph < WIND_NO_TRAVEL_BAND_MIN_MPH
        and load_weight_lb > WIND_SEVERE_LOAD_LB
    ):
        return RiskLevel.SEVERE, (
            f"Wind {wind_mph:.1f} mph with a {load_weight_lb:,} lb load triggers the "
            "35-44 mph / over 40,000 lb rule and is escalated to Severe."
        )
    return level, None


def assess_checkpoint_weather(
    weather: Optional[WeatherSample], load_weight_lb: float
) -> HazardAssessment:
    if weather is None or not weather.available:
        return HazardAssessment(
            wind=None, rain=None, snow=None, combined=None, no_travel_reason=None
        )

    reasons: List[str] = []
    wind_level: Optional[RiskLevel] = None
    rain_level: Optional[RiskLevel] = None
    snow_level: Optional[RiskLevel] = None

    if weather.wind_mph is not None:
        wind_level, wind_reason = assess_wind(weather.wind_mph, load_weight_lb)
        if wind_reason and wind_level is RiskLevel.NO_TRAVEL:
            reasons.append(wind_reason)

    if weather.rain_in_hr is not None:
        rain_level = classify_rain(weather.rain_in_hr)
        if rain_level is RiskLevel.NO_TRAVEL:
            reasons.append(
                f"Rain {weather.rain_in_hr:.2f} in/hr exceeds the 1.00 in/hr limit."
            )

    if weather.snow_in_hr is not None:
        snow_level = classify_snow(weather.snow_in_hr)
        if snow_level is RiskLevel.NO_TRAVEL:
            reasons.append(
                f"Snow {weather.snow_in_hr:.2f} in/hr exceeds the 3.0 in/hr limit."
            )

    combined = most_severe(wind_level, rain_level, snow_level)
    return HazardAssessment(
        wind=wind_level,
        rain=rain_level,
        snow=snow_level,
        combined=combined,
        no_travel_reason=" ".join(reasons) if reasons else None,
    )


def _represented_miles(checkpoints: Sequence[Checkpoint]) -> List[float]:
    distances = [checkpoint.cumulative_miles for checkpoint in checkpoints]
    represented: List[float] = []
    for index, distance in enumerate(distances):
        left = distances[index - 1] if index > 0 else distances[0]
        right = (
            distances[index + 1] if index < len(distances) - 1 else distances[-1]
        )
        represented.append(max(0.0, (right - left) / 2.0))
    return represented


def summarize_route(
    checkpoints: Sequence[Checkpoint], total_miles: float
) -> RouteRiskSummary:
    summary = RouteRiskSummary(total_miles=total_miles)
    represented = _represented_miles(checkpoints)

    buckets = {
        RiskLevel.LOW: "low_miles",
        RiskLevel.MODERATE: "moderate_miles",
        RiskLevel.HIGH: "high_miles",
        RiskLevel.SEVERE: "severe_miles",
        RiskLevel.NO_TRAVEL: "no_travel_miles",
    }

    weighted_total = 0.0
    weighted_miles = 0.0
    for checkpoint, miles in zip(checkpoints, represented):
        if checkpoint.combined_risk is None:
            summary.unknown_miles += miles
            continue
        attribute = buckets[checkpoint.combined_risk]
        setattr(summary, attribute, getattr(summary, attribute) + miles)
        weighted_total += RISK_NUMERIC[checkpoint.combined_risk.value] * miles
        weighted_miles += miles

    summary.low_miles = round(summary.low_miles, 3)
    summary.moderate_miles = round(summary.moderate_miles, 3)
    summary.high_miles = round(summary.high_miles, 3)
    summary.severe_miles = round(summary.severe_miles, 3)
    summary.no_travel_miles = round(summary.no_travel_miles, 3)
    summary.unknown_miles = round(summary.unknown_miles, 3)
    summary.average_risk = (
        round(weighted_total / weighted_miles, 4) if weighted_miles > 0.0 else 0.0
    )
    return summary
