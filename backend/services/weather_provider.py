from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

import requests

from .exceptions import WeatherProviderError

logger = logging.getLogger(__name__)

MM_PER_INCH = 25.4
CM_PER_INCH = 2.54
DEFAULT_TIMEOUT = float(os.getenv("WEATHER_TIMEOUT_SECONDS", "20"))
COORDINATE_PRECISION = 3
BATCH_SIZE = 25
WEATHER_ATTEMPTS = 3
BACKOFF_BASE_SECONDS = 1.0
BACKOFF_MAX_SECONDS = 20.0
RETRYABLE_STATUS = {429, 500, 502, 503, 504}
DEFAULT_USER_AGENT = "StormHaul/1.0 (+https://github.com/khelendrarauniyar/StormHaul)"
CUSTOMER_BASE_URL = "https://customer-api.open-meteo.com"
PUBLIC_BASE_URL = "https://api.open-meteo.com"

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


def user_agent() -> str:
    return os.getenv("WEATHER_USER_AGENT", DEFAULT_USER_AGENT)


def round_key(latitude: float, longitude: float) -> SeriesKey:
    return (round(latitude, COORDINATE_PRECISION), round(longitude, COORDINATE_PRECISION))


def api_key() -> str:
    return os.getenv("OPEN_METEO_API_KEY", "").strip()


def base_url() -> str:
    if api_key():
        return os.getenv("OPEN_METEO_CUSTOMER_BASE_URL", CUSTOMER_BASE_URL).rstrip("/")
    return os.getenv("WEATHER_BASE_URL", PUBLIC_BASE_URL).rstrip("/")


def sleep_backoff(attempt: int, headers: Optional[dict]) -> None:
    delay = BACKOFF_BASE_SECONDS * (2 ** attempt)
    if headers:
        retry_after = headers.get("Retry-After")
        if retry_after:
            try:
                delay = max(delay, float(retry_after))
            except (TypeError, ValueError):
                pass
    time.sleep(min(delay, BACKOFF_MAX_SECONDS))


class WeatherClient:
    name = "open-meteo"

    def __init__(self, forecast_days: int = 4, timeout: Optional[float] = None):
        self.forecast_days = forecast_days
        self.timeout = timeout or DEFAULT_TIMEOUT
        self._cache: Dict[SeriesKey, Dict[str, list]] = {}

    def fetch(self, points: Iterable[Tuple[float, float]]) -> Set[SeriesKey]:
        keys = self._unique_keys(points)
        succeeded: Set[SeriesKey] = set()
        for start in range(0, len(keys), BATCH_SIZE):
            batch = keys[start : start + BATCH_SIZE]
            try:
                self._fetch_batch(batch)
            except WeatherProviderError as exc:
                logger.warning("Open-Meteo batch failed: %s", exc)
                continue
            succeeded.update(batch)
        if keys and not succeeded:
            raise WeatherProviderError("Open-Meteo is unavailable.")
        return succeeded

    def _unique_keys(
        self, points: Iterable[Tuple[float, float]]
    ) -> List[SeriesKey]:
        keys: List[SeriesKey] = []
        seen: Set[SeriesKey] = set()
        for latitude, longitude in points:
            key = round_key(latitude, longitude)
            if key in self._cache or key in seen:
                continue
            seen.add(key)
            keys.append(key)
        return keys

    def _fetch_batch(self, batch: Sequence[SeriesKey]) -> None:
        params = {
            "latitude": ",".join(f"{lat:.4f}" for lat, _ in batch),
            "longitude": ",".join(f"{lon:.4f}" for _, lon in batch),
            "hourly": ",".join(HOURLY_FIELDS),
            "wind_speed_unit": "mph",
            "timezone": "GMT",
            "forecast_days": self.forecast_days,
        }
        key = api_key()
        if key:
            params["apikey"] = key

        response = self._request(f"{base_url()}/v1/forecast", params)
        try:
            payload = response.json()
        except ValueError as exc:
            raise WeatherProviderError("Open-Meteo returned malformed JSON.") from exc

        items = payload if isinstance(payload, list) else [payload]
        if len(items) != len(batch):
            raise WeatherProviderError(
                "Open-Meteo returned an unexpected number of locations."
            )

        for key, item in zip(batch, items):
            self._cache[key] = _parse_item(item)

    def _request(self, url: str, params: dict):
        headers = {"User-Agent": user_agent()}
        last_error: Optional[Exception] = None
        for attempt in range(WEATHER_ATTEMPTS):
            try:
                response = requests.get(
                    url, params=params, headers=headers, timeout=self.timeout
                )
                response.raise_for_status()
                return response
            except requests.HTTPError as exc:
                last_error = exc
                status = getattr(exc.response, "status_code", None)
                if status is not None and status not in RETRYABLE_STATUS:
                    logger.warning("Open-Meteo request failed: %s", exc)
                    raise WeatherProviderError("Open-Meteo is unavailable.") from exc
                if attempt < WEATHER_ATTEMPTS - 1:
                    sleep_backoff(attempt, getattr(exc.response, "headers", None))
            except requests.RequestException as exc:
                last_error = exc
                if attempt < WEATHER_ATTEMPTS - 1:
                    sleep_backoff(attempt, None)

        logger.warning("Open-Meteo request failed: %s", last_error)
        raise WeatherProviderError("Open-Meteo is unavailable.") from last_error

    def get(self, latitude: float, longitude: float) -> Optional[Dict[str, list]]:
        return self._cache.get(round_key(latitude, longitude))


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
