from __future__ import annotations

from typing import List, Sequence

from .models import RouteResult


def sort_key(route: RouteResult):
    summary = route.risk_summary
    return (
        0 if route.feasible else 1,
        summary.severe_miles,
        summary.high_miles,
        round(summary.average_risk, 6),
        route.duration_seconds,
        route.id,
    )


def rank_routes(routes: Sequence[RouteResult]) -> List[RouteResult]:
    return sorted(routes, key=sort_key)


def _format_miles(value: float) -> str:
    return f"{value:,.1f} mi"


def _format_duration(seconds: float) -> str:
    total_minutes = int(round(seconds / 60.0))
    hours, minutes = divmod(total_minutes, 60)
    if hours:
        return f"{hours} h {minutes} min"
    return f"{minutes} min"


def build_recommendation_reasons(
    routes: Sequence[RouteResult], recommended: RouteResult
) -> List[str]:
    reasons: List[str] = []
    feasible = [route for route in routes if route.feasible]
    prohibited = [route for route in routes if not route.feasible]

    if not recommended.feasible:
        reasons.append(
            "No feasible route was found: every alternative contains at least one "
            "No Travel segment. The route shown is only least-bad, not safe."
        )
        reasons.append(
            f"Least-bad option has {_format_miles(recommended.risk_summary.no_travel_miles)} "
            "of No Travel exposure."
        )
        return reasons

    if prohibited:
        reasons.append(
            f"{len(prohibited)} alternative(s) were excluded because they contain a "
            "No Travel segment."
        )

    summary = recommended.risk_summary
    others = [route for route in feasible if route.id != recommended.id]

    if others:
        if all(
            summary.severe_miles <= route.risk_summary.severe_miles for route in others
        ):
            reasons.append(
                f"{recommended.label} has the fewest Severe-risk miles "
                f"({_format_miles(summary.severe_miles)})."
            )
        if all(summary.high_miles <= route.risk_summary.high_miles for route in others):
            reasons.append(
                f"It has the fewest High-risk miles ({_format_miles(summary.high_miles)})."
            )
        if all(
            summary.average_risk <= route.risk_summary.average_risk for route in others
        ):
            reasons.append(
                f"It has the lowest distance-weighted average risk "
                f"({summary.average_risk:.2f} on a 0-4 scale)."
            )
        if all(summary.total_miles and recommended.duration_seconds <= route.duration_seconds for route in others):
            reasons.append(
                f"It is also the fastest option at {_format_duration(recommended.duration_seconds)}."
            )
        else:
            reasons.append(
                "Travel time was only used as a tie-breaker after risk mileage, per the "
                f"required priority order ({_format_duration(recommended.duration_seconds)})."
            )
    else:
        reasons.append(
            "Only one feasible route is available; it is presented with its risk breakdown."
        )

    if summary.unknown_miles > 0.0:
        reasons.append(
            f"Caution: {_format_miles(summary.unknown_miles)} of this route has no "
            "forecast coverage and was excluded from the risk totals."
        )

    if summary.no_travel_miles > 0.0:
        reasons.append(
            f"Caution: this route still includes {_format_miles(summary.no_travel_miles)} "
            "of No Travel exposure."
        )

    return reasons


def recommend(routes: Sequence[RouteResult]):
    ranked = rank_routes(routes)
    recommended = ranked[0]
    return recommended, build_recommendation_reasons(routes, recommended)
