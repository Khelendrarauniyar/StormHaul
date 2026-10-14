from datetime import datetime, timedelta, timezone
from unittest import mock

from django.test import TestCase
from rest_framework.test import APIClient

from services.exceptions import GeocodingError, GeocodingNotFound, ProviderError
from services.models import GeoPlace, RouteGeometry
DEPARTURE = datetime(2026, 10, 13, 8, 0, tzinfo=timezone.utc)


def _place(query):
    return GeoPlace(
        query=query, label=query, latitude=40.0, longitude=-105.0, source="test"
    )


def _routes():
    coordinates = [[-105.0, 40.0], [-111.8, 40.7]]
    return [
        RouteGeometry("Route A", coordinates, 520.0, 30000.0, "test"),
        RouteGeometry("Route B", coordinates, 540.0, 32000.0, "test"),
        RouteGeometry("Route C", coordinates, 560.0, 34000.0, "test"),
    ]


def _series():
    start = DEPARTURE - timedelta(hours=1)
    times = [start + timedelta(hours=index) for index in range(72)]
    return {
        "times": times,
        "wind_mph": [12.0] * 72,
        "rain_in_hr": [0.0] * 72,
        "snow_in_hr": [0.0] * 72,
        "temperature_c": [5.0] * 72,
        "gust_mph": [20.0] * 72,
    }


class FakeWeatherClient:
    def __init__(self, *args, **kwargs):
        pass

    def fetch(self, points):
        self.points = list(points)

    def get(self, latitude, longitude):
        return _series()


class RoutePlanApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.payload = {
            "origin": "Denver, CO",
            "destination": "Salt Lake City, UT",
            "departure_at": DEPARTURE.isoformat(),
            "load_weight_lb": 32000,
            "checkpoint_interval_miles": 25,
        }

    def test_health(self):
        response = self.client.get("/api/health/")
        self.assertEqual(response.status_code, 200)

    def test_successful_route_plan(self):
        with mock.patch("services.pipeline.geocode", side_effect=_place), mock.patch(
            "services.pipeline.get_alternatives", return_value=(_routes(), "test", [])
        ), mock.patch("services.pipeline.WeatherClient", FakeWeatherClient):
            response = self.client.post(
                "/api/route-plans/", self.payload, format="json"
            )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["routes"]), 3)
        self.assertIn("recommended_route_id", data)
        self.assertEqual(data["data_sources"]["routing"], "test")
        first_route = data["routes"][0]
        self.assertEqual(first_route["checkpoints"][0]["cumulative_miles"], 0.0)
        self.assertEqual(
            first_route["checkpoints"][-1]["cumulative_miles"], 520.0
        )
        self.assertTrue(
            all(checkpoint["combined_risk"] is not None for checkpoint in first_route["checkpoints"])
        )
        grid = data["grid"]
        self.assertEqual(len(grid["points"]), grid["rows"] * grid["columns"])
        self.assertTrue(all(len(point["wind_mph"]) == 48 for point in grid["points"]))

    def test_validation_error_shape(self):
        response = self.client.post("/api/route-plans/", {}, format="json")
        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertIn("error", body)
        self.assertEqual(body["error"]["code"], "validation_error")
        self.assertIn("origin", body["error"]["message"])

    def test_location_not_found_returns_422(self):
        with mock.patch(
            "services.pipeline.geocode",
            side_effect=GeocodingNotFound("Could not find a location for 'Nowhere'."),
        ):
            response = self.client.post(
                "/api/route-plans/", self.payload, format="json"
            )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "location_not_found")

    def test_location_search_returns_suggestions(self):
        places = [
            _place("Denver"),
            GeoPlace(
                "Salt Lake City",
                "Salt Lake City, Utah, United States",
                40.76,
                -111.89,
                "test",
            ),
        ]
        with mock.patch("routing.views.search_places", return_value=places):
            response = self.client.get("/api/locations/?q=den")
        self.assertEqual(response.status_code, 200)
        results = response.json()["results"]
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["label"], "Denver")
        self.assertIn("latitude", results[0])

    def test_location_search_short_query_returns_empty(self):
        response = self.client.get("/api/locations/?q=d")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"], [])

    def test_location_search_provider_failure_returns_empty(self):
        with mock.patch(
            "routing.views.search_places", side_effect=GeocodingError("down")
        ):
            response = self.client.get("/api/locations/?q=paris")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"], [])

    def test_coordinates_pass_through_without_geocoding(self):
        payload = dict(
            self.payload,
            origin_latitude=39.74,
            origin_longitude=-104.98,
            destination_latitude=40.76,
            destination_longitude=-111.89,
        )
        with mock.patch(
            "services.pipeline.geocode",
            side_effect=AssertionError("geocoding should be skipped"),
        ), mock.patch(
            "services.pipeline.get_alternatives", return_value=(_routes(), "test", [])
        ), mock.patch("services.pipeline.WeatherClient", FakeWeatherClient):
            response = self.client.post("/api/route-plans/", payload, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["origin"]["source"], "selected")

    def test_same_origin_and_destination_rejected(self):
        payload = dict(self.payload, destination="Denver, CO")
        response = self.client.post("/api/route-plans/", payload, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("destination", response.json()["error"]["details"])

    def test_invalid_interval_rejected(self):
        payload = dict(self.payload, checkpoint_interval_miles=15)
        response = self.client.post("/api/route-plans/", payload, format="json")
        self.assertEqual(response.status_code, 400)

    def test_provider_error_returns_502(self):
        with mock.patch(
            "services.pipeline.geocode",
            side_effect=ProviderError("geocoding down"),
        ):
            response = self.client.post(
                "/api/route-plans/", self.payload, format="json"
            )
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["error"]["code"], "provider_error")

    def test_weather_failure_degrades_gracefully(self):
        class BrokenWeatherClient:
            def __init__(self, *args, **kwargs):
                pass

            def fetch(self, points):
                from services.exceptions import WeatherProviderError

                raise WeatherProviderError("timeout")

            def get(self, latitude, longitude):
                return None

        with mock.patch("services.pipeline.geocode", side_effect=_place), mock.patch(
            "services.pipeline.get_alternatives", return_value=(_routes(), "test", [])
        ), mock.patch("services.pipeline.WeatherClient", BrokenWeatherClient):
            response = self.client.post(
                "/api/route-plans/", self.payload, format="json"
            )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data["weather_available"])
        self.assertIsNone(data["routes"][0]["checkpoints"][0]["combined_risk"])
        self.assertEqual(data["grid"]["points"], [])
