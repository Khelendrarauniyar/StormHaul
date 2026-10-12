from django.urls import include, path

from routing.views import HealthView

urlpatterns = [
    path("api/health/", HealthView.as_view(), name="health"),
    path("api/", include("routing.urls")),
]
