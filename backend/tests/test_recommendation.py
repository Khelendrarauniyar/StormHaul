from datetime import datetime, timezone

from django.test import SimpleTestCase

from services.models import RouteResult, RouteRiskSummary
from services.recommendation import build_recommendation_reasons, rank_routes, recommend


def make_route(
    route_id,
    severe=0.0,
    high=0.0,
    average=0.0,
    duration=3600.0,
    no_travel=0.0,
    feasible=True,
    label=None,
):
    summary = RouteRiskSummary(
        severe_miles=severe,
        high_miles=high,
        average_risk=average,
        no_travel_miles=no_travel,
        total_miles=500.0,
    )
    return RouteResult(
        id=route_id,
        label=label or route_id,
        source="test",
        coordinates=[[0.0, 0.0], [1.0, 1.0]],
        distance_miles=500.0,
        duration_seconds=duration,
        arrival_at=datetime(2026, 10, 13, tzinfo=timezone.utc),
        feasible=feasible,
        risk_summary=summary,
    )


class RankingTests(SimpleTestCase):
    def test_fewest_severe_wins_over_shorter_time(self):
        routes = [
            make_route("slow-safe", severe=5.0, duration=40000.0),
            make_route("fast-risky", severe=20.0, duration=30000.0),
        ]
        ranked = rank_routes(routes)
        self.assertEqual(ranked[0].id, "slow-safe")

    def test_high_miles_break_severe_tie(self):
        routes = [
            make_route("a", severe=5.0, high=30.0),
            make_route("b", severe=5.0, high=10.0),
        ]
        self.assertEqual(rank_routes(routes)[0].id, "b")

    def test_average_risk_breaks_high_tie(self):
        routes = [
            make_route("a", severe=5.0, high=10.0, average=2.0),
            make_route("b", severe=5.0, high=10.0, average=1.0),
        ]
        self.assertEqual(rank_routes(routes)[0].id, "b")

    def test_duration_breaks_average_tie(self):
        routes = [
            make_route("a", average=1.0, duration=4000.0),
            make_route("b", average=1.0, duration=3600.0),
        ]
        self.assertEqual(rank_routes(routes)[0].id, "b")

    def test_feasible_route_beats_prohibited_route(self):
        routes = [
            make_route("prohibited", no_travel=10.0, feasible=False),
            make_route("feasible", severe=50.0, feasible=True),
        ]
        self.assertEqual(rank_routes(routes)[0].id, "feasible")

    def test_deterministic_tie_break_by_id(self):
        routes = [make_route("b"), make_route("a")]
        self.assertEqual([route.id for route in rank_routes(routes)], ["a", "b"])


class RecommendationReasonTests(SimpleTestCase):
    def test_recommendation_reports_evidence(self):
        routes = [
            make_route("winner", severe=1.0, high=2.0, average=0.5, duration=3600.0, label="Route A"),
            make_route("other", severe=9.0, high=12.0, average=1.5, duration=3200.0, label="Route B"),
        ]
        recommended, reasons = recommend(routes)
        self.assertEqual(recommended.id, "winner")
        joined = " ".join(reasons)
        self.assertIn("Route A", joined)
        self.assertIn("Severe", joined)

    def test_no_feasible_route_is_reported(self):
        routes = [
            make_route("a", no_travel=5.0, feasible=False),
            make_route("b", no_travel=8.0, feasible=False),
        ]
        recommended, reasons = recommend(routes)
        self.assertFalse(recommended.feasible)
        self.assertTrue(any("No feasible route" in reason for reason in reasons))
