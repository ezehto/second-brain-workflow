from django.urls import path
from drf_spectacular.views import SpectacularAPIView
from rest_framework.permissions import IsAuthenticated

from api.views import auth, captures, dashboard, health, index, notes, projects, search, standups

urlpatterns = [
    path("health/", health.health, name="health"),
    path("auth/csrf/", auth.CsrfView.as_view(), name="auth-csrf"),
    path("auth/login/", auth.LoginView.as_view(), name="auth-login"),
    path("auth/logout/", auth.LogoutView.as_view(), name="auth-logout"),
    path("auth/me/", auth.MeView.as_view(), name="auth-me"),
    path("notes/", notes.NoteListCreateView.as_view(), name="notes"),
    path("notes/lookup/", notes.NoteLookupView.as_view(), name="notes-lookup"),
    path("notes/status/", notes.NoteStatusView.as_view(), name="notes-status"),
    path("captures/", captures.CaptureView.as_view(), name="captures"),
    path("captures/triage/", captures.TriageView.as_view(), name="captures-triage"),
    path("projects/", projects.ProjectListView.as_view(), name="projects"),
    path("projects/<slug:slug>/", projects.ProjectDetailView.as_view(), name="project-detail"),
    path("standups/today/", standups.StandupTodayView.as_view(), name="standups-today"),
    path("standups/today/append/", standups.StandupAppendView.as_view(), name="standups-append"),
    path("dashboard/", dashboard.DashboardView.as_view(), name="dashboard"),
    path("search/", search.SearchView.as_view(), name="search"),
    path("index/status/", index.IndexStatusView.as_view(), name="index-status"),
    path("index/refresh/", index.IndexRefreshView.as_view(), name="index-refresh"),
    # Session-authenticated (the project's default authentication); spectacular's own default
    # would be AllowAny.
    path(
        "schema/",
        SpectacularAPIView.as_view(permission_classes=[IsAuthenticated]),
        name="schema",
    ),
]
