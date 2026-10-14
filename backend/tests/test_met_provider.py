from datetime import datetime, timezone

from django.test import SimpleTestCase

from services.met_provider import MPS_TO_MPH, _parse_timeseries


def _payload():
    return {
        "properties": {
            "timeseries": [
                {
                    "time": "2026-10-13T08:00:00Z",
                    "data": {
                        "instant": {
                            "details": {"air_temperature": 5.0, "wind_speed": 10.0}
                        },
                        "next_1_hours": {
                            "summary": {"symbol_code": "rain"},
                            "details": {"precipitation_amount": 2.54},
                        },
                    },
                },
                {
                    "time": "2026-10-13T09:00:00Z",
                    "data": {
                        "instant": {
                            "details": {"air_temperature": -3.0, "wind_speed": 20.0}
                        },
                        "next_1_hours": {
                            "summary": {"symbol_code": "snow"},
                            "details": {"precipitation_amount": 25.4},
                        },
                    },
                },
                {
                    "time": "2026-10-13T10:00:00Z",
                    "data": {
                        "instant": {
                            "details": {"air_temperature": 1.0, "wind_speed": 5.0}
                        },
                        "next_6_hours": {
                            "summary": {"symbol_code": "cloudy"},
                            "details": {"precipitation_amount": 0.0},
                        },
                    },
                },
                {
                    "time": "2026-10-13T11:00:00Z",
                    "data": {"instant": {"details": {"air_temperature": 1.0, "wind_speed": 5.0}}},
                },
            ]
        }
    }


class ParseMetNoTests(SimpleTestCase):
    def test_times_are_utc_aware(self):
        series = _parse_timeseries(_payload())
        self.assertEqual(len(series["times"]), 4)
        self.assertEqual(series["times"][0], datetime(2026, 10, 13, 8, 0, tzinfo=timezone.utc))

    def test_wind_converted_from_mps_to_mph(self):
        series = _parse_timeseries(_payload())
        self.assertAlmostEqual(series["wind_mph"][0], 10.0 * MPS_TO_MPH)
        self.assertAlmostEqual(series["wind_mph"][1], 20.0 * MPS_TO_MPH)

    def test_rain_and_snow_split_by_symbol(self):
        series = _parse_timeseries(_payload())
        self.assertAlmostEqual(series["rain_in_hr"][0], 0.1)
        self.assertAlmostEqual(series["snow_in_hr"][0], 0.0)
        self.assertAlmostEqual(series["rain_in_hr"][1], 0.0)
        self.assertAlmostEqual(series["snow_in_hr"][1], 1.0)

    def test_six_hour_block_is_averaged_to_hourly_rate(self):
        series = _parse_timeseries(_payload())
        self.assertAlmostEqual(series["rain_in_hr"][2], 0.0)
        self.assertAlmostEqual(series["snow_in_hr"][2], 0.0)

    def test_missing_precipitation_is_none(self):
        series = _parse_timeseries(_payload())
        self.assertIsNone(series["rain_in_hr"][3])
        self.assertIsNone(series["snow_in_hr"][3])
