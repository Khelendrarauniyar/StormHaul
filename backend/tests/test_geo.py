from django.test import SimpleTestCase

from services.geo import (
    cumulative_miles,
    haversine_miles,
    interpolate,
    sample_along_route,
    simplify_line,
)


class HaversineTests(SimpleTestCase):
    def test_one_degree_latitude(self):
        distance = haversine_miles(40.0, -105.0, 41.0, -105.0)
        self.assertAlmostEqual(distance, 69.09, delta=0.5)

    def test_same_point_is_zero(self):
        self.assertEqual(haversine_miles(40.0, -105.0, 40.0, -105.0), 0.0)


class CumulativeTests(SimpleTestCase):
    def test_cumulative_is_monotonic(self):
        coordinates = [[-105.0, 40.0], [-105.0, 40.5], [-105.0, 41.0]]
        cumulative = cumulative_miles(coordinates)
        self.assertEqual(cumulative[0], 0.0)
        self.assertEqual(cumulative, sorted(cumulative))


class InterpolateTests(SimpleTestCase):
    def setUp(self):
        self.coordinates = [[-105.0, 40.0], [-105.0, 41.0]]
        self.cumulative = cumulative_miles(self.coordinates)

    def test_start_point(self):
        lat, lon = interpolate(self.coordinates, self.cumulative, 0.0)
        self.assertAlmostEqual(lat, 40.0, places=6)
        self.assertAlmostEqual(lon, -105.0, places=6)

    def test_end_point(self):
        lat, lon = interpolate(self.coordinates, self.cumulative, self.cumulative[-1])
        self.assertAlmostEqual(lat, 41.0, places=6)

    def test_midpoint(self):
        target = self.cumulative[-1] / 2.0
        lat, _ = interpolate(self.coordinates, self.cumulative, target)
        self.assertAlmostEqual(lat, 40.5, places=3)


class SampleAlongRouteTests(SimpleTestCase):
    def test_respects_max_points(self):
        coordinates = [[-105.0, 40.0 + index * 0.01] for index in range(200)]
        samples = sample_along_route(coordinates, 1.0, max_points=40)
        self.assertLessEqual(len(samples), 41)
        self.assertEqual(samples[0][2], 0.0)


class SimplifyLineTests(SimpleTestCase):
    def test_collinear_points_collapse_to_endpoints(self):
        coordinates = [[-105.0, 40.0 + index * 0.001] for index in range(21)]
        simplified = simplify_line(coordinates, 0.0005)
        self.assertEqual(simplified, [coordinates[0], coordinates[-1]])

    def test_endpoints_are_always_kept(self):
        coordinates = [[-105.0, 40.0], [-105.0, 40.0001], [-105.0, 41.0]]
        simplified = simplify_line(coordinates, 0.01)
        self.assertEqual(simplified[0], coordinates[0])
        self.assertEqual(simplified[-1], coordinates[-1])

    def test_significant_vertex_is_preserved(self):
        coordinates = [[-105.0, 40.0], [-104.0, 40.5], [-105.0, 41.0]]
        simplified = simplify_line(coordinates, 0.0005)
        self.assertEqual(len(simplified), 3)

    def test_short_line_returned_unchanged(self):
        coordinates = [[-105.0, 40.0], [-105.0, 41.0]]
        self.assertEqual(simplify_line(coordinates, 0.01), coordinates)

