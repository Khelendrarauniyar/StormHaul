from unittest import mock

from django.test import SimpleTestCase

from services.exceptions import WeatherProviderError
from services.weather_provider import round_key
from services.weather_service import TOTAL_DEADLINE, WeatherService, build_weather_service


def _series():
    return {"times": [], "wind_mph": [10.0], "rain_in_hr": [0.0], "snow_in_hr": [0.0]}


class FakeProvider:
    name = "fake"

    def __init__(self, keys=(), working=True):
        self._keys = {round_key(lat, lon) for lat, lon in keys}
        self._working = working
        self._cache = {}
        self.calls = []

    def fetch(self, points):
        self.calls.append(list(points))
        if not self._working:
            raise WeatherProviderError(f"{self.name} is down")
        resolved = set()
        for key in points:
            if key in self._keys:
                self._cache[key] = _series()
                resolved.add(key)
        return resolved

    def get(self, latitude, longitude):
        return self._cache.get(round_key(latitude, longitude))


class WeatherServiceTests(SimpleTestCase):
    def test_uses_primary_when_it_covers_everything(self):
        primary = FakeProvider(keys=[(40.0, -105.0)])
        primary.name = "open-meteo"
        fallback = FakeProvider(keys=[(40.0, -105.0)])
        fallback.name = "met-no"

        service = WeatherService([primary, fallback])
        service.fetch([(40.0, -105.0)])

        self.assertEqual(service.sources, ["open-meteo"])
        self.assertEqual(service.source_for(40.0, -105.0), "open-meteo")
        self.assertEqual(fallback.calls, [])

    def test_falls_back_for_unresolved_points(self):
        primary = FakeProvider(keys=[(40.0, -105.0)])
        primary.name = "open-meteo"
        fallback = FakeProvider(keys=[(41.0, -106.0)])
        fallback.name = "met-no"

        service = WeatherService([primary, fallback])
        service.fetch([(40.0, -105.0), (41.0, -106.0)])

        self.assertEqual(service.sources, ["open-meteo", "met-no"])
        self.assertEqual(service.source_for(40.0, -105.0), "open-meteo")
        self.assertEqual(service.source_for(41.0, -106.0), "met-no")

    def test_raises_when_no_provider_succeeds(self):
        primary = FakeProvider(working=False)
        primary.name = "open-meteo"
        fallback = FakeProvider(working=False)
        fallback.name = "met-no"

        service = WeatherService([primary, fallback])
        with self.assertRaises(WeatherProviderError):
            service.fetch([(40.0, -105.0)])

    def test_default_service_orders_primary_then_fallback(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            service = build_weather_service()
        self.assertEqual(service.providers, ["open-meteo", "met-no"])

    def test_bounds_each_provider_by_the_total_budget(self):
        class DeadlineProvider(FakeProvider):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.deadline = None

        primary = DeadlineProvider(keys=[(40.0, -105.0)])
        primary.name = "open-meteo"
        fallback = DeadlineProvider(keys=[(41.0, -106.0)])
        fallback.name = "met-no"

        service = WeatherService([primary, fallback])
        service.fetch([(40.0, -105.0), (41.0, -106.0)])

        self.assertIsNotNone(primary.deadline)
        self.assertGreater(primary.deadline, 0)
        self.assertLessEqual(primary.deadline, TOTAL_DEADLINE)
        self.assertLessEqual(fallback.deadline, TOTAL_DEADLINE)
