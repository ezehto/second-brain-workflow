"""Django settings, read entirely from the environment (plan section 6, P1-17)."""

import os
from collections.abc import Mapping
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY_PLACEHOLDER = "change-me-not-a-secret"
SECRET_KEY_MIN_LENGTH = 50  # Django's own check (security.W009) uses the same threshold


def env_bool(name: str, default: bool = False, environ: Mapping[str, str] = os.environ) -> bool:
    """Read a boolean flag; only 1/true/yes/on (any case) are true."""
    value = environ.get(name)
    if value is None or not value.strip():
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, environ: Mapping[str, str] = os.environ) -> list[str]:
    """Read a comma-separated list, dropping blanks."""
    return [item.strip() for item in environ.get(name, "").split(",") if item.strip()]


def get_secret_key(environ: Mapping[str, str] = os.environ) -> str:
    """Return DJANGO_SECRET_KEY, refusing a missing, empty, placeholder or short value."""
    key = environ.get("DJANGO_SECRET_KEY", "").strip()
    if not key:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY is not set; put a long random value in .env")
    if key == SECRET_KEY_PLACEHOLDER:
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY is still the .env.example placeholder; generate a random value"
        )
    if len(key) < SECRET_KEY_MIN_LENGTH:
        raise ImproperlyConfigured(
            f"DJANGO_SECRET_KEY is shorter than {SECRET_KEY_MIN_LENGTH} characters"
        )
    return key


SECRET_KEY = get_secret_key()
DEBUG = env_bool("DJANGO_DEBUG", False)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.postgres",
    "rest_framework",
    "drf_spectacular",
    "vault",
    "api",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", ""),
        "USER": os.environ.get("POSTGRES_USER", ""),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
        "HOST": os.environ.get("POSTGRES_HOST", "db"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

TIME_ZONE = os.environ.get("TZ") or "Asia/Manila"
USE_TZ = True
LANGUAGE_CODE = "en-us"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# The vault as seen from inside the container; tests point this at a temp dir.
VAULT_ROOT = os.environ.get("VAULT_ROOT", "/vault")
INDEXER_POLL_SECONDS = int(os.environ.get("INDEXER_POLL_SECONDS", "10"))

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

# SameSite=Lax; the session cookie is HttpOnly (the CSRF cookie must stay readable by the
# client). SECURE_* settings wait for a later task: the stack is HTTP on localhost.
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"plain": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"}},
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
            "formatter": "plain",
        }
    },
    "root": {"handlers": ["console"], "level": "INFO"},
}
