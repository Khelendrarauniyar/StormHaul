from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from services.exceptions import GeocodingError, GeocodingNotFound, ProviderError
from services.pipeline import build_route_plan
from services.routing_provider import search_places

from .serializers import RoutePlanRequestSerializer


class HealthView(APIView):
    def get(self, request):
        return Response({"status": "ok", "service": "stormhaul"})


class LocationSearchView(APIView):
    def get(self, request):
        query = (request.query_params.get("q") or "").strip()
        if len(query) < 2:
            return Response({"results": []})
        try:
            places = search_places(query)
        except GeocodingError:
            return Response({"results": []})
        return Response(
            {
                "results": [
                    {
                        "label": place.label,
                        "latitude": round(place.latitude, 6),
                        "longitude": round(place.longitude, 6),
                    }
                    for place in places
                ]
            }
        )


class RoutePlanView(APIView):
    def post(self, request):
        serializer = RoutePlanRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            payload = build_route_plan(serializer.validated_data)
        except GeocodingNotFound as exc:
            return Response(
                {
                    "error": {
                        "code": "location_not_found",
                        "message": str(exc),
                        "details": {},
                    }
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        except ProviderError as exc:
            return Response(
                {
                    "error": {
                        "code": "provider_error",
                        "message": str(exc),
                        "details": {},
                    }
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )
        return Response(payload, status=status.HTTP_200_OK)
