"""Settings come from the environment and refuse unsafe defaults."""

import importlib

import pytest
from django.apps import apps
from django.core.exceptions import ImproperlyConfigured

from config import settings as settings_module
from config.settings import SECRET_KEY_PLACEHOLDER, get_secret_key


def reload_settings(settings_env, **env):
    for name, value in env.items():
        if value is None:
            settings_env.delenv(name, raising=False)
        else:
            settings_env.setenv(name, value)
    return importlib.reload(settings_module)


@pytest.fixture
def settings_env():
    """A monkeypatch whose undo runs before config.settings is reloaded back to the real env."""
    patch = pytest.MonkeyPatch()
    yield patch
    patch.undo()
    importlib.reload(settings_module)


@pytest.mark.parametrize("environ", [{}, {"DJANGO_SECRET_KEY": ""}, {"DJANGO_SECRET_KEY": "  "}])
def test_secret_key_missing_is_refused(environ):
    with pytest.raises(ImproperlyConfigured, match="not set"):
        get_secret_key(environ)


def test_secret_key_placeholder_is_refused():
    with pytest.raises(ImproperlyConfigured, match="placeholder"):
        get_secret_key({"DJANGO_SECRET_KEY": SECRET_KEY_PLACEHOLDER})


def test_secret_key_shorter_than_50_chars_is_refused():
    with pytest.raises(ImproperlyConfigured, match="shorter than 50"):
        get_secret_key({"DJANGO_SECRET_KEY": "x" * 49})


def test_secret_key_real_value_is_accepted():
    assert get_secret_key({"DJANGO_SECRET_KEY": "x" * 50}) == "x" * 50


def test_settings_module_refuses_to_load_without_key(settings_env):
    settings_env.delenv("DJANGO_SECRET_KEY", raising=False)
    with pytest.raises(ImproperlyConfigured):
        importlib.reload(settings_module)


def test_settings_module_refuses_placeholder_key(settings_env):
    settings_env.setenv("DJANGO_SECRET_KEY", SECRET_KEY_PLACEHOLDER)
    with pytest.raises(ImproperlyConfigured):
        importlib.reload(settings_module)


def test_debug_is_false_by_default(settings_env):
    loaded = reload_settings(settings_env, DJANGO_DEBUG=None)
    assert loaded.DEBUG is False


@pytest.mark.parametrize(("value", "expected"), [("true", True), ("1", True), ("false", False)])
def test_debug_reads_environment(settings_env, value, expected):
    assert reload_settings(settings_env, DJANGO_DEBUG=value).DEBUG is expected


def test_time_zone_comes_from_tz(settings_env):
    assert reload_settings(settings_env, TZ="Europe/Paris").TIME_ZONE == "Europe/Paris"


def test_time_zone_defaults_to_manila(settings_env):
    loaded = reload_settings(settings_env, TZ=None)
    assert loaded.TIME_ZONE == "Asia/Manila"
    assert loaded.USE_TZ is True


def test_comma_lists_and_defaults(settings_env):
    loaded = reload_settings(
        settings_env,
        DJANGO_ALLOWED_HOSTS="localhost, 127.0.0.1,,",
        CSRF_TRUSTED_ORIGINS="http://localhost:5173",
        VAULT_ROOT=None,
        POSTGRES_HOST=None,
    )
    assert loaded.ALLOWED_HOSTS == ["localhost", "127.0.0.1"]
    assert loaded.CSRF_TRUSTED_ORIGINS == ["http://localhost:5173"]
    assert loaded.VAULT_ROOT == "/vault"
    assert loaded.DATABASES["default"]["HOST"] == "db"


def test_cookie_settings(settings):
    assert settings.SESSION_COOKIE_SAMESITE == "Lax"
    assert settings.CSRF_COOKIE_SAMESITE == "Lax"
    assert settings.SESSION_COOKIE_HTTPONLY is True


def test_drf_defaults(settings):
    drf = settings.REST_FRAMEWORK
    assert drf["DEFAULT_RENDERER_CLASSES"] == ["rest_framework.renderers.JSONRenderer"]
    assert drf["DEFAULT_PERMISSION_CLASSES"] == ["rest_framework.permissions.IsAuthenticated"]
    assert drf["DEFAULT_AUTHENTICATION_CLASSES"] == [
        "rest_framework.authentication.SessionAuthentication"
    ]
    assert drf["DEFAULT_SCHEMA_CLASS"] == "drf_spectacular.openapi.AutoSchema"


def test_admin_is_not_installed(settings):
    assert "django.contrib.admin" not in settings.INSTALLED_APPS
    assert not apps.is_installed("django.contrib.admin")


def test_project_apps_are_installed():
    assert apps.is_installed("vault")
    assert apps.is_installed("api")
