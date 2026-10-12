from django.urls import path

from .views import LocationSearchView, RoutePlanView

urlpatterns = [
    path("route-plans/", RoutePlanView.as_view(), name="route-plans"),
    path("locations/", LocationSearchView.as_view(), name="locations"),
]
