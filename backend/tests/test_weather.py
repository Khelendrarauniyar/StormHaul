from unittest.mock import Mock, patch

import requests
from django.test import SimpleTestCase

from services.exceptions import WeatherProviderError
from services.weather_provider import (
    CM_PER_INCH,
    MM_PER_INCH,
    WEATHER_ATTEMPTS,
    WeatherClient,
    _parse_item,
)


class ParseWeatherItemTests(SimpleTestCase):
    def test_rain_combines_rain_and_showers_and_converts_units(self):
        item = {
            "hourly": {
                "time": ["2026-10-12T00:00"],
                "rain": [2.54],
                "showers": [2.54],
                "snowfall": [2.54],
                "wind_speed_10m": [10.0],
                "wind_gusts_10m": [20.0],
                "temperature_2m": [5.0],
            }
        }
        parsed = _parse_item(item)
        self.assertAlmostEqual(parsed["rain_in_hr"][0], (2.54 + 2.54) / MM_PER_INCH)
        self.assertAlmostEqual(parsed["rain_in_hr"][0], 0.2)
        self.assertAlmostEqual(parsed["snow_in_hr"][0], 2.54 / CM_PER_INCH)
        self.assertAlmostEqual(parsed["snow_in_hr"][0], 1.0)

    def test_showers_count_toward_rain(self):
        item = {
            "hourly": {
                "time": ["2026-10-12T00:00"],
                "rain": [0.0],
                "showers": [1.27],
                "snowfall": [0.0],
            }
        }
        parsed = _parse_item(item)
        self.assertAlmostEqual(parsed["rain_in_hr"][0], 1.27 / MM_PER_INCH)

    def test_missing_values_stay_none(self):
        item = {
            "hourly": {
                "time": ["2026-10-12T00:00"],
                "rain": [None],
                "showers": [None],
                "snowfall": [None],
            }
        }
        parsed = _parse_item(item)
        self.assertIsNone(parsed["rain_in_hr"][0])
        self.assertIsNone(parsed["snow_in_hr"][0])


class WeatherRetryTests(SimpleTestCase):
    def _payload(self):
        return {
            "hourly": {
                "time": ["2026-10-12T00:00"],
                "rain": [0.0],
                "showers": [0.0],
                "snowfall": [0.0],
                "wind_speed_10m": [10.0],
                "wind_gusts_10m": [15.0],
                "temperature_2m": [10.0],
            }
        }

    @patch("services.weather_provider.time.sleep", return_value=None)
    @patch("services.weather_provider.requests.get")
    def test_retries_then_succeeds(self, get, _sleep):
        failing = Mock()
        failing.raise_for_status.side_effect = requests.ConnectionError("boom")
        succeeding = Mock()
        succeeding.raise_for_status.return_value = None
        succeeding.json.return_value = self._payload()
        get.side_effect = [failing, succeeding]

        client = WeatherClient()
        client.fetch([(40.0, -105.0)])

        self.assertIsNotNone(client.get(40.0, -105.0))
        self.assertEqual(get.call_count, 2)

    @patch("services.weather_provider.time.sleep", return_value=None)
    @patch("services.weather_provider.requests.get")
    def test_raises_after_all_attempts(self, get, _sleep):
        failing = Mock()
        failing.raise_for_status.side_effect = requests.ConnectionError("boom")
        get.return_value = failing

        client = WeatherClient()
        with self.assertRaises(WeatherProviderError):
            client.fetch([(40.0, -105.0)])

        self.assertEqual(get.call_count, WEATHER_ATTEMPTS)

    @patch("services.weather_provider.time.sleep", return_value=None)
    @patch("services.weather_provider.requests.get")
    def test_retries_on_server_error_then_succeeds(self, get, _sleep):
        faulty = Mock()
        response = requests.Response()
        response.status_code = 503
        faulty.raise_for_status.side_effect = requests.HTTPError(response=response)
        succeeding = Mock()
        succeeding.raise_for_status.return_value = None
        succeeding.json.return_value = self._payload()
        get.side_effect = [faulty, succeeding]

        client = WeatherClient()
        client.fetch([(40.0, -105.0)])

        self.assertIsNotNone(client.get(40.0, -105.0))
        self.assertEqual(get.call_count, 2)

    @patch("services.weather_provider.time.sleep", return_value=None)
    @patch("services.weather_provider.requests.get")
    def test_rate_limit_fails_fast_without_retry(self, get, _sleep):
        throttled = Mock()
        response = requests.Response()
        response.status_code = 429
        throttled.raise_for_status.side_effect = requests.HTTPError(response=response)
        get.return_value = throttled

        client = WeatherClient()
        with self.assertRaises(WeatherProviderError):
            client.fetch([(40.0, -105.0)])

        self.assertEqual(get.call_count, 1)

    @patch("services.weather_provider.requests.get")
    def test_does_not_retry_on_client_error(self, get):
        rejected = Mock()
        response = requests.Response()
        response.status_code = 400
        rejected.raise_for_status.side_effect = requests.HTTPError(response=response)
        get.return_value = rejected

        client = WeatherClient()
        with self.assertRaises(WeatherProviderError):
            client.fetch([(40.0, -105.0)])

        self.assertEqual(get.call_count, 1)
