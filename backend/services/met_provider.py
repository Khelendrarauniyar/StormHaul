from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError, as_completed
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple

import requests

from .exceptions import WeatherProviderError
from .weather_provider import (
    MM_PER_INCH,
    SeriesKey,
    WEATHER_ATTEMPTS,
    round_key,
    sleep_backoff,
    user_agent,
)

logger = logging.getLogger(__name__)

MPS_TO_MPH = 2.2369362920544
ROUNDING_DEGREES = 4
DEFAULT_BASE_URL = "https://api.met.no"
DEFAULT_TIMEOUT = float(os.getenv("WEATHER_TIMEOUT_SECONDS", "20"))
DEFAULT_WORKERS = int(os.getenv("MET_NO_WORKERS", "16"))
DEFAULT_DEADLINE = float(os.getenv("MET_NO_DEADLINE_SECONDS", "25"))
RETRYABLE_STATUS = {429, 500, 502, 503, 504}
SNOW_TOKENS = ("snow", "sleet")


def base_url() -> str:
    return os.getenv("MET_NO_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


class MetNoClient:
    name = "met-no"

    def __init__(self, timeout: Optional[float] = None, max_workers: Optional[int] = None):
        self.timeout = timeout or DEFAULT_TIMEOUT
        self.max_workers = max_workers or DEFAULT_WORKERS
        self.deadline = DEFAULT_DEADLINE
        self._cache: Dict[SeriesKey, Dict[str, list]] = {}

    def fetch(self, points) -> Set[SeriesKey]:
        keys = self._unique_keys(points)
        if not keys:
            return set()
        pool = ThreadPoolExecutor(max_workers=self.max_workers)
        futures = {pool.submit(self._fetch_one, key): key for key in keys}
        try:
            for future in as_completed(futures, timeout=self.deadline):
                key = futures[future]
                try:
                    series = future.result()
                except WeatherProviderError as exc:
                    logger.warning("MET Norway location failed: %s", exc)
                    continue
                if series is not None:
                    self._cache[key] = series
        except TimeoutError:
            logger.warning(
                "MET Norway deadline of %.1fs reached; returning partial coverage.",
                self.deadline,
            )
        finally:
            pool.shutdown(wait=False, cancel_futures=True)
        succeeded = {key for key in keys if key in self._cache}
        if not succeeded:
            raise WeatherProviderError("MET Norway is unavailable.")
        return succeeded

    def _unique_keys(self, points) -> List[SeriesKey]:
        keys: List[SeriesKey] = []
        seen: Set[SeriesKey] = set()
        for latitude, longitude in points:
            key = round_key(latitude, longitude)
            if key in self._cache or key in seen:
                continue
            seen.add(key)
            keys.append(key)
        return keys

    def _fetch_one(self, key: SeriesKey) -> Dict[str, list]:
        latitude, longitude = key
        params = {"lat": round(latitude, ROUNDING_DEGREES), "lon": round(longitude, ROUNDING_DEGREES)}
        headers = {"User-Agent": user_agent(), "Accept": "application/json"}
        url = f"{base_url()}/weatherapi/locationforecast/2.0/compact"
        last_error: Optional[Exception] = None
        for attempt in range(WEATHER_ATTEMPTS):
            try:
                response = requests.get(
                    url, params=params, headers=headers, timeout=self.timeout
                )
                response.raise_for_status()
                payload = response.json()
                return _parse_timeseries(payload)
            except ValueError as exc:
                raise WeatherProviderError("MET Norway returned malformed JSON.") from exc
            except requests.HTTPError as exc:
                last_error = exc
                status = getattr(exc.response, "status_code", None)
                if status is not None and status not in RETRYABLE_STATUS:
                    raise WeatherProviderError("MET Norway is unavailable.") from exc
                if attempt < WEATHER_ATTEMPTS - 1:
                    sleep_backoff(attempt, getattr(exc.response, "headers", None))
            except requests.RequestException as exc:
                last_error = exc
                if attempt < WEATHER_ATTEMPTS - 1:
                    sleep_backoff(attempt, None)
        raise WeatherProviderError("MET Norway is unavailable.") from last_error

    def get(self, latitude: float, longitude: float) -> Optional[Dict[str, list]]:
        return self._cache.get(round_key(latitude, longitude))


def _parse_timeseries(payload: dict) -> Dict[str, list]:
    series = (payload.get("properties") or {}).get("timeseries") or []
    times: List[datetime] = []
    wind_mph: List[Optional[float]] = []
    gust_mph: List[Optional[float]] = []
    temperature_c: List[Optional[float]] = []
    rain_in_hr: List[Optional[float]] = []
    snow_in_hr: List[Optional[float]] = []

    for entry in series:
        moment = _parse_time(entry.get("time"))
        if moment is None:
            continue
        details = ((entry.get("data") or {}).get("instant") or {}).get("details") or {}
        times.append(moment)
        speed = details.get("wind_speed")
        wind_mph.append(None if speed is None else float(speed) * MPS_TO_MPH)
        gust_mph.append(None)
        air = details.get("air_temperature")
        temperature_c.append(None if air is None else float(air))
        rain, snow = _precipitation_rate(entry.get("data") or {})
        rain_in_hr.append(rain)
        snow_in_hr.append(snow)

    return {
        "times": times,
        "wind_mph": wind_mph,
        "gust_mph": gust_mph,
        "temperature_c": temperature_c,
        "rain_in_hr": rain_in_hr,
        "snow_in_hr": snow_in_hr,
    }


def _precipitation_rate(data: dict) -> Tuple[Optional[float], Optional[float]]:
    for key, hours in (("next_1_hours", 1), ("next_6_hours", 6), ("next_12_hours", 12)):
        block = data.get(key)
        if not block:
            continue
        amount = (block.get("details") or {}).get("precipitation_amount")
        if amount is None:
            continue
        symbol = (block.get("summary") or {}).get("symbol_code") or ""
        rate = float(amount) / hours / MM_PER_INCH
        if any(token in symbol for token in SNOW_TOKENS):
            return 0.0, rate
        return rate, 0.0
    return None, None


def _parse_time(value) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None
