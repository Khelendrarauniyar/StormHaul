from __future__ import annotations

import logging
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError, as_completed
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, Optional, Set, Tuple

import requests

from .exceptions import WeatherProviderError
from .weather_provider import MM_PER_INCH, SeriesKey, round_key, sleep_backoff, user_agent

logger = logging.getLogger(__name__)

BASE_URL = "https://api.weather.gov"
KMH_PER_MPH = 1.609344
DEFAULT_TIMEOUT = float(os.getenv("WEATHER_TIMEOUT_SECONDS", "20"))
DEFAULT_WORKERS = int(os.getenv("NWS_WORKERS", "20"))
DEFAULT_DEADLINE = float(os.getenv("NWS_DEADLINE_SECONDS", "15"))
RETRYABLE_STATUS = {500, 502, 503, 504}
DURATION_PATTERN = re.compile(r"^P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?)?$")


def base_url() -> str:
    return os.getenv("NWS_BASE_URL", BASE_URL).rstrip("/")


class NwsClient:
    name = "nws"

    def __init__(self, timeout: Optional[float] = None, max_workers: Optional[int] = None):
        self.timeout = timeout or DEFAULT_TIMEOUT
        self.max_workers = max_workers or DEFAULT_WORKERS
        self.deadline = DEFAULT_DEADLINE
        self._cache: Dict[SeriesKey, Dict[str, list]] = {}
        self._local = threading.local()

    def _session(self) -> requests.Session:
        session = getattr(self._local, "session", None)
        if session is None:
            session = requests.Session()
            session.headers.update(
                {"User-Agent": user_agent(), "Accept": "application/geo+json"}
            )
            self._local.session = session
        return session

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
                    logger.warning("NWS location failed: %s", exc)
                    continue
                if series:
                    self._cache[key] = series
        except TimeoutError:
            logger.warning(
                "NWS deadline of %.1fs reached; returning partial coverage.",
                self.deadline,
            )
        finally:
            pool.shutdown(wait=False, cancel_futures=True)
        if keys and not self._cache:
            raise WeatherProviderError("NWS is unavailable.")
        return set(self._cache)

    def _unique_keys(self, points) -> list:
        keys = []
        seen: Set[SeriesKey] = set()
        for latitude, longitude in points:
            key = round_key(latitude, longitude)
            if key in self._cache or key in seen:
                continue
            seen.add(key)
            keys.append(key)
        return keys

    def _fetch_one(self, key: SeriesKey) -> Optional[Dict[str, list]]:
        latitude, longitude = key
        session = self._session()
        grid_url = self._grid_url(session, latitude, longitude)
        if grid_url is None:
            return None
        response = self._get(session, grid_url)
        if response is None:
            return None
        try:
            payload = response.json()
        except ValueError as exc:
            raise WeatherProviderError("NWS returned malformed JSON.") from exc
        return _grid_series((payload or {}).get("properties") or {})

    def _grid_url(self, session, latitude: float, longitude: float) -> Optional[str]:
        url = f"{BASE_URL}/points/{round(latitude, 4)},{round(longitude, 4)}"
        response = self._get(session, url, allow_404=True)
        if response is None:
            return None
        try:
            properties = (response.json() or {}).get("properties") or {}
        except ValueError as exc:
            raise WeatherProviderError("NWS returned malformed JSON.") from exc
        return properties.get("forecastGridData")

    def _get(
        self, session: requests.Session, url: str, allow_404: bool = False
    ) -> Optional[requests.Response]:
        last_error: Optional[Exception] = None
        for attempt in range(2):
            try:
                response = session.get(url, timeout=self.timeout)
                if allow_404 and response.status_code == 404:
                    return None
                response.raise_for_status()
                return response
            except requests.HTTPError as exc:
                last_error = exc
                status = getattr(exc.response, "status_code", None)
                if status is not None and status not in {500, 502, 503, 504}:
                    raise WeatherProviderError("NWS is unavailable.") from exc
                if attempt < 1:
                    sleep_backoff(attempt, getattr(exc.response, "headers", None))
            except requests.RequestException as exc:
                last_error = exc
                if attempt < 1:
                    sleep_backoff(attempt, None)
        raise WeatherProviderError("NWS is unavailable.") from last_error

    def get(self, latitude: float, longitude: float) -> Optional[Dict[str, list]]:
        return self._cache.get(round_key(latitude, longitude))


def _grid_series(properties: dict) -> Optional[Dict[str, list]]:
    wind = _hourly_map(properties.get("windSpeed"), lambda value, hours: value / KMH_PER_MPH)
    gust = _hourly_map(properties.get("windGust"), lambda value, hours: value / KMH_PER_MPH)
    temperature = _hourly_map(properties.get("temperature"), lambda value, hours: value)
    rain = _hourly_map(
        properties.get("quantitativePrecipitation"),
        lambda value, hours: value / hours / MM_PER_INCH,
    )
    snow = _hourly_map(
        properties.get("snowfallAmount"),
        lambda value, hours: value / hours / MM_PER_INCH,
    )

    buckets = sorted(set().union(*[set(mapping) for mapping in (wind, gust, temperature, rain, snow)]))
    if not buckets:
        return None
    return {
        "times": buckets,
        "wind_mph": [wind.get(bucket) for bucket in buckets],
        "gust_mph": [gust.get(bucket) for bucket in buckets],
        "temperature_c": [temperature.get(bucket) for bucket in buckets],
        "rain_in_hr": [rain.get(bucket) for bucket in buckets],
        "snow_in_hr": [snow.get(bucket) for bucket in buckets],
    }


def _hourly_map(block: Optional[dict], transform: Callable[[float, int], float]) -> Dict[datetime, float]:
    result: Dict[datetime, float] = {}
    for item in (block or {}).get("values") or []:
        valid_time = item.get("validTime")
        value = item.get("value")
        if valid_time is None or value is None:
            continue
        start, hours = _parse_valid_time(valid_time)
        if start is None:
            continue
        per_hour = transform(float(value), hours)
        for offset in range(hours):
            result[start + timedelta(hours=offset)] = per_hour
    return result


def _parse_valid_time(value: str) -> Tuple[Optional[datetime], int]:
    if "/" not in value:
        return None, 0
    start_text, duration = value.split("/", 1)
    try:
        start = datetime.fromisoformat(start_text.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None, 0
    return start, _duration_hours(duration)


def _duration_hours(value: str) -> int:
    match = re.match(r"^P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?)?$", value.strip())
    if not match:
        return 1
    days = int(match.group(1) or 0)
    hours = int(match.group(2) or 0)
    minutes = int(match.group(3) or 0)
    total = days * 24 + hours
    if minutes > 0:
        total += 1
    return max(1, total)
