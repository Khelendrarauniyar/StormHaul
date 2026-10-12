from datetime import datetime, timedelta, timezone

from django.test import SimpleTestCase

from services.checkpoints import build_checkpoints, checkpoint_targets


class CheckpointTargetTests(SimpleTestCase):
    def test_exact_multiples(self):
        self.assertEqual(checkpoint_targets(100.0, 25.0), [0.0, 25.0, 50.0, 75.0, 100.0])
        self.assertEqual(checkpoint_targets(100.0, 50.0), [0.0, 50.0, 100.0])

    def test_final_partial_segment(self):
        self.assertEqual(checkpoint_targets(100.0, 30.0), [0.0, 30.0, 60.0, 90.0, 100.0])

    def test_short_route_shorter_than_interval(self):
        self.assertEqual(checkpoint_targets(2.0, 10.0), [0.0, 2.0])

    def test_zero_length_route(self):
        self.assertEqual(checkpoint_targets(0.0, 10.0), [0.0])


class BuildCheckpointTests(SimpleTestCase):
    def setUp(self):
        self.departure = datetime(2026, 10, 13, 8, 0, tzinfo=timezone.utc)
        self.coordinates = [[-105.0, 40.0], [-105.0, 40.5], [-105.0, 41.0]]

    def test_endpoints_and_count(self):
        checkpoints = build_checkpoints(
            self.coordinates, 100.0, 3600.0, self.departure, 25.0
        )
        self.assertEqual(checkpoints[0].cumulative_miles, 0.0)
        self.assertEqual(checkpoints[-1].cumulative_miles, 100.0)
        self.assertEqual(len(checkpoints), 5)
        self.assertEqual(
            [checkpoint.sequence for checkpoint in checkpoints], [0, 1, 2, 3, 4]
        )

    def test_arrival_interpolation(self):
        checkpoints = build_checkpoints(
            self.coordinates, 100.0, 3600.0, self.departure, 25.0
        )
        self.assertEqual(checkpoints[0].arrival_at, self.departure)
        midpoint = checkpoints[2]
        self.assertEqual(midpoint.arrival_at, self.departure + timedelta(seconds=1800))
        self.assertEqual(
            checkpoints[-1].arrival_at, self.departure + timedelta(seconds=3600)
        )

    def test_arrival_times_monotonic(self):
        checkpoints = build_checkpoints(
            self.coordinates, 100.0, 3600.0, self.departure, 10.0
        )
        arrivals = [checkpoint.arrival_at for checkpoint in checkpoints]
        self.assertEqual(arrivals, sorted(arrivals))
