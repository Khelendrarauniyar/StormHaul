from django.test import SimpleTestCase

from services.grid import (
    GRID_MAX_POINTS,
    GRID_MIN_DIM,
    build_grid,
    grid_dimensions,
    grid_points,
    padded_bounds,
    route_bounds,
    union_bounds,
)


class RouteBoundsTests(SimpleTestCase):
    def test_bounds_wrap_all_coordinates(self):
        coordinates = [[-105.0, 40.0], [-111.8, 40.7], [-108.0, 39.5]]
        south, north, west, east = route_bounds(coordinates)
        self.assertEqual(south, 39.5)
        self.assertEqual(north, 40.7)
        self.assertEqual(west, -111.8)
        self.assertEqual(east, -105.0)

    def test_empty_coordinates_return_none(self):
        self.assertIsNone(route_bounds([]))


class UnionBoundsTests(SimpleTestCase):
    def test_union_covers_every_route(self):
        bounds = union_bounds(
            [
                (40.0, 41.0, -105.0, -104.0),
                (39.0, 40.5, -108.0, -106.0),
                None,
            ]
        )
        self.assertEqual(bounds, (39.0, 41.0, -108.0, -104.0))

    def test_all_empty_returns_none(self):
        self.assertIsNone(union_bounds([None, None]))


class PaddedBoundsTests(SimpleTestCase):
    def test_padding_expands_every_edge(self):
        padded = padded_bounds((40.0, 41.0, -105.0, -104.0))
        self.assertLess(padded[0], 40.0)
        self.assertGreater(padded[1], 41.0)
        self.assertLess(padded[2], -105.0)
        self.assertGreater(padded[3], -104.0)


class GridDimensionTests(SimpleTestCase):
    def test_respects_max_points(self):
        rows, columns = grid_dimensions((39.0, 41.0, -112.0, -104.0))
        self.assertLessEqual(rows * columns, GRID_MAX_POINTS)

    def test_keeps_minimum_dimensions_for_tiny_area(self):
        rows, columns = grid_dimensions((40.0, 40.0001, -105.0, -105.0001))
        self.assertGreaterEqual(rows, GRID_MIN_DIM)
        self.assertGreaterEqual(columns, GRID_MIN_DIM)


class GridPointTests(SimpleTestCase):
    def test_grid_points_stay_inside_bounds(self):
        bounds = (39.0, 41.0, -112.0, -104.0)
        points, latitude_step, longitude_step = grid_points(bounds, 8, 12)
        self.assertEqual(len(points), 96)
        self.assertGreater(latitude_step, 0.0)
        self.assertGreater(longitude_step, 0.0)
        for latitude, longitude in points:
            self.assertGreaterEqual(latitude, bounds[0])
            self.assertLessEqual(latitude, bounds[1])
            self.assertGreaterEqual(longitude, bounds[2])
            self.assertLessEqual(longitude, bounds[3])


class BuildGridTests(SimpleTestCase):
    def test_point_count_matches_dimensions(self):
        grid = build_grid((40.0, 40.7, -111.8, -105.0))
        self.assertEqual(grid["rows"] * grid["columns"], len(grid["points"]))
        self.assertLessEqual(len(grid["points"]), GRID_MAX_POINTS)

    def test_bounds_contain_original_extent(self):
        grid = build_grid((40.0, 40.7, -111.8, -105.0))
        self.assertLess(grid["bounds"]["south"], 40.0)
        self.assertGreater(grid["bounds"]["north"], 40.7)
        self.assertLess(grid["bounds"]["west"], -111.8)
        self.assertGreater(grid["bounds"]["east"], -105.0)

    def test_spacing_is_positive(self):
        grid = build_grid((40.0, 40.7, -111.8, -105.0))
        self.assertGreater(grid["spacing_latitude"], 0.0)
        self.assertGreater(grid["spacing_longitude"], 0.0)
