"""
Django settings for Bambicim project.
Django 5.2.x
"""

from __future__ import annotations

import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

# ------------------------------------------------------------------------------
# Paths & env helper
# ------------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")  # optional; safe if file missing


def env(key: str, default=None, cast=str):
    """Tiny env helper (keeps working even if python-decouple not installed)."""
    val = os.getenv(key, default)
    if cast is bool:
        return str(val).lower() in {"1", "true", "yes", "on"}
    if cast is int:
        try:
            return int(val)  # type: ignore[arg-type]
        except Exception:
            return int(default) if default is not None else None
    if cast is list:
        return [x.strip() for x in str(val or "").split(",") if x.strip()]
    return val


# ------------------------------------------------------------------------------
# Core
# ------------------------------------------------------------------------------
# Tip: set DJANGO_SECRET_KEY in prod to a long, random value (>= 50 chars).
SECRET_KEY = env("DJANGO_SECRET_KEY", default="dev-secret-unsafe-DO_NOT_USE_IN_PRODUCTION")

# In local dev we default to DEBUG=True; in CI/prod set DJANGO_DEBUG=0
# (On GitHub Actions we default DEBUG to False so `check --deploy` passes.)
_ci_default = "0" if os.getenv("GITHUB_ACTIONS") else "1"
DEBUG: bool = env("DJANGO_DEBUG", default=_ci_default, cast=bool)

ALLOWED_HOSTS = env(
    "ALLOWED_HOSTS",
    default="bambicim.com,www.bambicim.com,.onrender.com,127.0.0.1,localhost",
    cast=list,
)

CSRF_TRUSTED_ORIGINS = env(
    "CSRF_TRUSTED_ORIGINS",
    default="https://bambicim.com,https://www.bambicim.com,https://*.onrender.com",
    cast=list,
)

# Used by your templates/logic if you care about a single “canonical” host.
CANONICAL_HOST = env("CANONICAL_HOST", default="bambicim.com")

# ------------------------------------------------------------------------------
# Security (kept strict when DEBUG=False, lenient in dev)
# ------------------------------------------------------------------------------
if not DEBUG:
    # Redirect http→https behind a proxy (Render/NGINX, etc.)
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

    # HSTS: start with 30d if you want to be cautious; 1y is common in prod
    SECURE_HSTS_SECONDS = env("SECURE_HSTS_SECONDS", default=60 * 60 * 24 * 365, cast=int)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
else:
    # In dev we don’t force https/hsts.
    SECURE_SSL_REDIRECT = False
    SECURE_PROXY_SSL_HEADER = None
    SECURE_HSTS_SECONDS = 0
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_PRELOAD = False

# Good general defaults
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# ------------------------------------------------------------------------------
# Apps
# ------------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",

    # WhiteNoise: keep *before* staticfiles
    "whitenoise.runserver_nostatic",

    "django.contrib.staticfiles",
    "django.contrib.sitemaps",

    # Project apps
    "core.apps.BambiConfig",
    "accounts",
    "portfolio",
    "copilot",
    "blog",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.middleware.TrafficMiddleware",
]

ROOT_URLCONF = "Bambicim.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "portfolio.context_processors.featured_projects",
            ],
        },
    },
]

WSGI_APPLICATION = "Bambicim.wsgi.application"

# ------------------------------------------------------------------------------
# Database
# ------------------------------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL", "")

if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=600,
            ssl_require=os.getenv("DJANGO_DB_SSL") == "1",
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# ------------------------------------------------------------------------------
# Password validation
# ------------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ------------------------------------------------------------------------------
# i18n / tz
# ------------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ------------------------------------------------------------------------------
# Static & media
# ------------------------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Optional project-level static dir (loaded only if it exists)
STATICFILES_DIRS = [p for p in [
    BASE_DIR / "static",
    BASE_DIR / "core" / "static",
] if p.exists()]

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Django 4.2+ storages API (WhiteNoise)
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",  # media
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# (Optional) still okay to set this; harmless with STORAGES above
if not DEBUG:
    STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# ------------------------------------------------------------------------------
# Feature flags / misc
# ------------------------------------------------------------------------------
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
BAMBI_COPILOT_ENABLED = True

# OpenAI (safe defaults)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
BMB_MODEL = os.getenv("BMB_MODEL", "gpt-4o-mini")
BMB_SYS_PERSONA = os.getenv("BMB_SYS_PERSONA", "")

# ------------------------------------------------------------------------------
# Email
# ------------------------------------------------------------------------------
EMAIL_BACKEND = (
        os.getenv("EMAIL_BACKEND")
        or (
            "django.core.mail.backends.console.EmailBackend" if DEBUG else "django.core.mail.backends.smtp.EmailBackend")
)
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = env("EMAIL_PORT", default=587, cast=int)
EMAIL_USE_TLS = env("EMAIL_USE_TLS", default=True, cast=bool)
EMAIL_USE_SSL = env("EMAIL_USE_SSL", default=False, cast=bool)
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER or "noreply@bambicim.com")
CONTACT_RECIPIENT = os.getenv("CONTACT_RECIPIENT", DEFAULT_FROM_EMAIL)
EMAIL_TIMEOUT = 20

# ------------------------------------------------------------------------------
# Logging (simple, quiet by default)
# ------------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {"format": "[{levelname}] {asctime} {name} - {message}", "style": "{"},
        "simple": {"format": "[{levelname}] {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"},
    },
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO" if not DEBUG else "INFO", "propagate": True},
        "app": {"handlers": ["console"], "level": "INFO"},
    },
}
