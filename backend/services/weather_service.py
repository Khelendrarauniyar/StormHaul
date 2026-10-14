from __future__ import annotations

import logging
import os
from typing import Dict, Iterable, List, Optional, Set, Tuple

from .exceptions import WeatherProviderError
from .met_provider import MetNoClient
from .weather_provider import SeriesKey, WeatherClient, round_key

logger = logging.getLogger(__name__)


class WeatherService:
    def __init__(self, providers: List):
        self._providers = providers
        self._series: Dict[SeriesKey, Dict[str, list]] = {}
        self._owner: Dict[SeriesKey, str] = {}

    @property
    def providers(self) -> List[str]:
        return [provider.name for provider in self._providers]

    @property
    def sources(self) -> List[str]:
        used = set(self._owner.values())
        return [name for name in self.providers if name in used]

    def fetch(self, points: Iterable[Tuple[float, float]]) -> None:
        pending = self._pending_keys(points)
        for provider in self._providers:
            if not pending:
                break
            try:
                succeeded = provider.fetch(pending)
            except WeatherProviderError as exc:
                logger.warning("%s unavailable: %s", provider.name, exc)
                succeeded = set()
            resolved: Set[SeriesKey] = set()
            for key in succeeded:
                series = provider.get(*key)
                if series is None:
                    continue
                self._series[key] = series
                self._owner[key] = provider.name
                resolved.add(key)
            unresolved = [key for key in pending if key not in resolved]
            if unresolved:
                logger.info(
                    "%s resolved %d/%d points; %d left for fallback",
                    provider.name,
                    len(resolved),
                    len(pending),
                    len(unresolved),
                )
            pending = unresolved

        if not self._series:
            raise WeatherProviderError("All weather providers were unavailable.")

    def _pending_keys(self, points: Iterable[Tuple[float, float]]) -> List[SeriesKey]:
        keys: List[SeriesKey] = []
        seen: Set[SeriesKey] = set()
        for latitude, longitude in points:
            key = round_key(latitude, longitude)
            if key in self._series or key in seen:
                continue
            seen.add(key)
            keys.append(key)
        return keys

    def get(self, latitude: float, longitude: float) -> Optional[Dict[str, list]]:
        return self._series.get(round_key(latitude, longitude))

    def source_for(self, latitude: float, longitude: float) -> Optional[str]:
        return self._owner.get(round_key(latitude, longitude))


def build_weather_service() -> WeatherService:
    names: List[str] = []
    for name in (
        os.getenv("WEATHER_PROVIDER", "open-meteo").strip().lower(),
        os.getenv("WEATHER_FALLBACK_PROVIDER", "met-no").strip().lower(),
    ):
        if name and name not in names:
            names.append(name)

    providers = []
    for name in names:
        provider = _make_provider(name)
        if provider is not None:
            providers.append(provider)
    return WeatherService(providers)


def _make_provider(name: str):
    if name == "open-meteo":
        return WeatherClient()
    if name in {"met-no", "metno", "met"}:
        return MetNoClient()
    logger.warning("Unknown weather provider '%s'", name)
    return None
