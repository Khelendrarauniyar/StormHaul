from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import requests

from .exceptions import WeatherProviderError

logger = logging.getLogger(__name__)

MM_PER_INCH = 25.4
CM_PER_INCH = 2.54
DEFAULT_TIMEOUT = float(os.getenv("WEATHER_TIMEOUT_SECONDS", "20"))
COORDINATE_PRECISION = 3
BATCH_SIZE = 25
WEATHER_ATTEMPTS = 3

HOURLY_FIELDS = (
    "temperature_2m",
    "wind_speed_10m",
    "wind_gusts_10m",
    "rain",
    "showers",
    "snowfall",
    "precipitation",
)

SeriesKey = Tuple[float, float]


class WeatherClient:
    def __init__(self, forecast_days: int = 4, timeout: Optional[float] = None):
        self.forecast_days = forecast_days
        self.timeout = timeout or DEFAULT_TIMEOUT
        self._cache: Dict[SeriesKey, Dict[str, list]] = {}

    def fetch(self, points: Iterable[Tuple[float, float]]) -> None:
        keys: List[SeriesKey] = []
        seen = set()
        for latitude, longitude in points:
            key = (round(latitude, COORDINATE_PRECISION), round(longitude, COORDINATE_PRECISION))
            if key in self._cache or key in seen:
                continue
            seen.add(key)
            keys.append(key)

        for start in range(0, len(keys), BATCH_SIZE):
            batch = keys[start : start + BATCH_SIZE]
            self._fetch_batch(batch)

    def _fetch_batch(self, batch: Sequence[SeriesKey]) -> None:
        base = os.getenv("WEATHER_BASE_URL", "https://api.open-meteo.com").rstrip("/")
        params = {
            "latitude": ",".join(f"{lat:.4f}" for lat, _ in batch),
            "longitude": ",".join(f"{lon:.4f}" for _, lon in batch),
            "hourly": ",".join(HOURLY_FIELDS),
            "wind_speed_unit": "mph",
            "timezone": "GMT",
            "forecast_days": self.forecast_days,
        }
        payload = None
        for attempt in range(WEATHER_ATTEMPTS):
            try:
                response = requests.get(
                    f"{base}/v1/forecast", params=params, timeout=self.timeout
                )
                response.raise_for_status()
                payload = response.json()
                break
            except requests.RequestException as exc:
                if attempt < WEATHER_ATTEMPTS - 1:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                logger.warning("Open-Meteo request failed: %s", exc)
                raise WeatherProviderError("Open-Meteo is unavailable.") from exc
            except ValueError as exc:
                raise WeatherProviderError("Open-Meteo returned malformed JSON.") from exc

        items = payload if isinstance(payload, list) else [payload]
        if len(items) != len(batch):
            raise WeatherProviderError(
                "Open-Meteo returned an unexpected number of locations."
            )

        for key, item in zip(batch, items):
            self._cache[key] = _parse_item(item)

    def get(self, latitude: float, longitude: float) -> Optional[Dict[str, list]]:
        key = (round(latitude, COORDINATE_PRECISION), round(longitude, COORDINATE_PRECISION))
        return self._cache.get(key)


def _parse_item(item: dict) -> Dict[str, list]:
    hourly = item.get("hourly", {})
    times = [
        datetime.fromisoformat(value).replace(tzinfo=timezone.utc)
        for value in hourly.get("time", [])
    ]
    rain = hourly.get("rain", [])
    showers = hourly.get("showers", [])
    snow = hourly.get("snowfall", [])
    return {
        "times": times,
        "wind_mph": _clean(hourly.get("wind_speed_10m", [])),
        "gust_mph": _clean(hourly.get("wind_gusts_10m", [])),
        "temperature_c": _clean(hourly.get("temperature_2m", [])),
        "rain_in_hr": _combine([rain, showers], MM_PER_INCH),
        "snow_in_hr": _convert(snow, CM_PER_INCH),
    }


def _clean(values: Sequence[Optional[float]]) -> List[Optional[float]]:
    return [None if value is None else float(value) for value in values or []]


def _combine(series_list: Sequence[Sequence[Optional[float]]], divisor: float) -> List[Optional[float]]:
    length = max((len(series) for series in series_list), default=0)
    combined: List[Optional[float]] = []
    for index in range(length):
        total = 0.0
        seen = False
        for series in series_list:
            value = series[index] if index < len(series) else None
            if value is None:
                continue
            total += float(value)
            seen = True
        combined.append(total / divisor if seen else None)
    return combined


def _convert(values: Sequence[Optional[float]], divisor: float) -> List[Optional[float]]:
    return [
        None if value is None else float(value) / divisor for value in values or []
    ]


def floor_to_hour(moment: datetime) -> datetime:
    moment = moment.astimezone(timezone.utc)
    return moment.replace(minute=0, second=0, microsecond=0)


def hour_index(series: Dict[str, list], moment: datetime) -> Optional[int]:
    bucket = floor_to_hour(moment)
    times = series.get("times", [])
    try:
        return times.index(bucket)
    except ValueError:
        return None


def value_at(series: Optional[Dict[str, list]], field: str, moment: datetime):
    if not series:
        return None
    index = hour_index(series, moment)
    if index is None:
        return None
    values = series.get(field, [])
    if index >= len(values):
        return None
    return values[index]


def align_series(
    series: Optional[Dict[str, list]], start: datetime, hours: int
) -> Tuple[List[Optional[float]], List[Optional[float]], List[Optional[float]]]:
    wind: List[Optional[float]] = []
    rain: List[Optional[float]] = []
    snow: List[Optional[float]] = []
    for offset in range(hours):
        moment = start + timedelta(hours=offset)
        wind.append(value_at(series, "wind_mph", moment))
        rain.append(value_at(series, "rain_in_hr", moment))
        snow.append(value_at(series, "snow_in_hr", moment))
    return wind, rain, snow
