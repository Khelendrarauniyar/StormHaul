from datetime import datetime, timezone

from django.test import SimpleTestCase

from services.nws_provider import _duration_hours, _grid_series, _parse_valid_time


def _properties():
    return {
        "windSpeed": {
            "uom": "wmoUnit:km_h-1",
            "values": [{"validTime": "2026-10-15T00:00:00+00:00/PT1H", "value": 16.09344}],
        },
        "windGust": {
            "uom": "wmoUnit:km_h-1",
            "values": [{"validTime": "2026-10-15T00:00:00+00:00/PT1H", "value": 32.18688}],
        },
        "temperature": {
            "uom": "wmoUnit:degC",
            "values": [{"validTime": "2026-10-15T00:00:00+00:00/PT1H", "value": 7.5}],
        },
        "quantitativePrecipitation": {
            "uom": "wmoUnit:mm",
            "values": [{"validTime": "2026-10-15T00:00:00+00:00/PT6H", "value": 152.4}],
        },
        "snowfallAmount": {
            "uom": "wmoUnit:mm",
            "values": [{"validTime": "2026-10-15T00:00:00+00:00/PT6H", "value": 0}],
        },
    }


class ParseNwsTests(SimpleTestCase):
    def test_wind_converted_from_kmh_to_mph(self):
        series = _grid_series(_properties())
        self.assertAlmostEqual(series["wind_mph"][0], 10.0)
        self.assertAlmostEqual(series["gust_mph"][0], 20.0)

    def test_precipitation_spread_as_hourly_rate(self):
        series = _grid_series(_properties())
        self.assertAlmostEqual(series["rain_in_hr"][0], 1.0)
        self.assertAlmostEqual(series["snow_in_hr"][0], 0.0)

    def test_interval_becomes_hourly_buckets(self):
        series = _grid_series(_properties())
        self.assertEqual(len(series["times"]), 6)
        self.assertEqual(series["times"][0], datetime(2026, 10, 15, 0, 0, tzinfo=timezone.utc))

    def test_missing_fields_yield_none(self):
        self.assertIsNone(_grid_series({}))

    def test_duration_hours(self):
        self.assertEqual(_duration_hours("PT1H"), 1)
        self.assertEqual(_duration_hours("PT6H"), 6)
        self.assertEqual(_duration_hours("P1D"), 24)
        self.assertEqual(_duration_hours("P1DT6H"), 30)

    def test_valid_time_parsing(self):
        start, hours = _parse_valid_time("2026-10-15T06:00:00+00:00/PT3H")
        self.assertEqual(start, datetime(2026, 10, 15, 6, 0, tzinfo=timezone.utc))
        self.assertEqual(hours, 3)
