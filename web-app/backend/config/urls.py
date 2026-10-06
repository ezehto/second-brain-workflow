"""Root URL configuration: everything is served under /api/."""

from django.urls import include, path

urlpatterns = [
    path("api/", include("api.urls")),
]
