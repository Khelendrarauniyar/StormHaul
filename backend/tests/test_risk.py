from django.test import SimpleTestCase

from services.risk import (
    assess_wind,
    classify_rain,
    classify_snow,
    classify_wind,
    summarize_route,
)
from services.models import Checkpoint, RiskLevel, WeatherSample
from services.risk import assess_checkpoint_weather


class WindClassificationTests(SimpleTestCase):
    def test_wind_boundaries(self):
        cases = [
            (0.0, RiskLevel.LOW),
            (24.9, RiskLevel.LOW),
            (25.0, RiskLevel.MODERATE),
            (34.9, RiskLevel.MODERATE),
            (35.0, RiskLevel.HIGH),
            (44.9, RiskLevel.HIGH),
            (45.0, RiskLevel.SEVERE),
            (54.9, RiskLevel.SEVERE),
            (55.0, RiskLevel.NO_TRAVEL),
            (80.0, RiskLevel.NO_TRAVEL),
        ]
        for value, expected in cases:
            with self.subTest(value=value):
                self.assertEqual(classify_wind(value), expected)


class RainClassificationTests(SimpleTestCase):
    def test_rain_boundaries(self):
        cases = [
            (0.0, RiskLevel.LOW),
            (0.099, RiskLevel.LOW),
            (0.10, RiskLevel.MODERATE),
            (0.249, RiskLevel.MODERATE),
            (0.25, RiskLevel.HIGH),
            (0.499, RiskLevel.HIGH),
            (0.50, RiskLevel.SEVERE),
            (1.00, RiskLevel.SEVERE),
            (1.01, RiskLevel.NO_TRAVEL),
        ]
        for value, expected in cases:
            with self.subTest(value=value):
                self.assertEqual(classify_rain(value), expected)


class SnowClassificationTests(SimpleTestCase):
    def test_snow_boundaries(self):
        cases = [
            (0.0, RiskLevel.LOW),
            (0.499, RiskLevel.LOW),
            (0.5, RiskLevel.MODERATE),
            (0.999, RiskLevel.MODERATE),
            (1.0, RiskLevel.HIGH),
            (1.999, RiskLevel.HIGH),
            (2.0, RiskLevel.SEVERE),
            (3.0, RiskLevel.SEVERE),
            (3.01, RiskLevel.NO_TRAVEL),
        ]
        for value, expected in cases:
            with self.subTest(value=value):
                self.assertEqual(classify_snow(value), expected)


class LoadRuleTests(SimpleTestCase):
    def test_severe_wind_no_travel_for_any_load(self):
        level, reason = assess_wind(55.0, 0)
        self.assertEqual(level, RiskLevel.NO_TRAVEL)
        self.assertIsNotNone(reason)

    def test_45_mph_at_30000_lb_stays_severe(self):
        level, _ = assess_wind(45.0, 30_000)
        self.assertEqual(level, RiskLevel.SEVERE)

    def test_45_mph_above_30000_lb_is_no_travel(self):
        level, reason = assess_wind(45.0, 30_001)
        self.assertEqual(level, RiskLevel.NO_TRAVEL)
        self.assertIn("30,000", reason)

    def test_35_mph_at_40000_lb_stays_high(self):
        level, _ = assess_wind(35.0, 40_000)
        self.assertEqual(level, RiskLevel.HIGH)

    def test_35_mph_above_40000_lb_is_severe(self):
        level, reason = assess_wind(35.0, 40_001)
        self.assertEqual(level, RiskLevel.SEVERE)
        self.assertIn("40,000", reason)

    def test_low_wind_is_unaffected_by_load(self):
        level, reason = assess_wind(20.0, 80_000)
        self.assertEqual(level, RiskLevel.LOW)
        self.assertIsNone(reason)


class CombinedRiskTests(SimpleTestCase):
    def _sample(self, wind, rain, snow):
        return WeatherSample(
            wind_mph=wind,
            rain_in_hr=rain,
            snow_in_hr=snow,
            temperature_c=0.0,
            observed_at=None,
            available=True,
            source="test",
        )

    def test_severe_snow_dominates_low_wind(self):
        assessment = assess_checkpoint_weather(self._sample(10.0, 0.0, 2.5), 10_000)
        self.assertEqual(assessment.combined, RiskLevel.SEVERE)

    def test_missing_weather_is_unknown(self):
        assessment = assess_checkpoint_weather(None, 10_000)
        self.assertIsNone(assessment.combined)

    def test_no_travel_reason_present(self):
        assessment = assess_checkpoint_weather(self._sample(60.0, 0.0, 0.0), 10_000)
        self.assertEqual(assessment.combined, RiskLevel.NO_TRAVEL)
        self.assertTrue(assessment.no_travel_reason)


class SummarizeRouteTests(SimpleTestCase):
    def _checkpoint(self, sequence, miles, risk):
        return Checkpoint(
            sequence=sequence,
            latitude=0.0,
            longitude=0.0,
            cumulative_miles=miles,
            arrival_at=None,
            combined_risk=risk,
        )

    def test_risk_mileage_and_weighted_average(self):
        checkpoints = [
            self._checkpoint(0, 0.0, RiskLevel.LOW),
            self._checkpoint(1, 10.0, RiskLevel.HIGH),
            self._checkpoint(2, 20.0, RiskLevel.LOW),
        ]
        summary = summarize_route(checkpoints, 20.0)
        self.assertAlmostEqual(summary.low_miles, 10.0, places=3)
        self.assertAlmostEqual(summary.high_miles, 10.0, places=3)
        self.assertAlmostEqual(summary.total_miles, 20.0, places=3)
        self.assertAlmostEqual(summary.average_risk, (0 * 10 + 2 * 10) / 20, places=4)

    def test_unknown_miles_tracked(self):
        checkpoints = [
            self._checkpoint(0, 0.0, None),
            self._checkpoint(1, 10.0, RiskLevel.LOW),
        ]
        summary = summarize_route(checkpoints, 10.0)
        self.assertAlmostEqual(summary.unknown_miles, 5.0, places=3)
        self.assertAlmostEqual(summary.low_miles, 5.0, places=3)
