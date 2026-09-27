"""Base Django settings shared by every environment. Configuration comes from env vars (§34)."""

from __future__ import annotations

import os
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def env(name: str, default: str | None = None) -> str:
    value = os.environ.get(name)
    return default if value is None or value == "" else value  # type: ignore[return-value]


def env_bool(name: str, default: bool = False) -> bool:
    return env(name, "1" if default else "0").strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    return int(env(name, str(default)))


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in env(name, default).split(",") if item.strip()]


SECRET_KEY = env("DJANGO_SECRET_KEY", "dev-insecure-secret-key")
DEBUG = env_bool("DJANGO_DEBUG", False)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")

APP_URL = env("APP_URL", "http://localhost:5173")
FRONTEND_URL = env("FRONTEND_URL", "http://localhost:5173")

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "corsheaders",
    "rest_framework",
    "drf_spectacular",
    # bounded contexts
    "shared_kernel.apps.SharedKernelConfig",
    "identity.apps.IdentityConfig",
    "gmail_integration.apps.GmailIntegrationConfig",
    "mailbox_context.apps.MailboxConfig",
    "email_intelligence.apps.EmailIntelligenceConfig",
    # dev tooling (demo seed) — composes all contexts, not itself a bounded context
    "demo.apps.DemoConfig",
]

# Migrations live next to the ORM models in each context's infrastructure/persistence package.
MIGRATION_MODULES = {
    "identity": "identity.infrastructure.persistence.migrations",
    "gmail_integration": "gmail_integration.infrastructure.persistence.migrations",
    "mailbox": "mailbox_context.infrastructure.persistence.migrations",
    "email_intelligence": "email_intelligence.infrastructure.persistence.migrations",
}

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
APPEND_SLASH = False

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": dj_database_url.parse(
        env("DATABASE_URL", "postgres://emp:emp@localhost:5432/emp"), conn_max_age=60
    )
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "identity.UserModel"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# --- CORS / CSRF / sessions (SPA uses session cookies + CSRF through the Vite proxy) ---
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", FRONTEND_URL)
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", FRONTEND_URL)
SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", False)
CSRF_COOKIE_SECURE = env_bool("CSRF_COOKIE_SECURE", False)
SESSION_COOKIE_SAMESITE = env("SESSION_COOKIE_SAMESITE", "Lax")
CSRF_COOKIE_SAMESITE = SESSION_COOKIE_SAMESITE
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14
CSRF_COOKIE_HTTPONLY = False  # SPA reads csrftoken cookie and echoes it in X-CSRFToken

# --- DRF ---
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "shared_kernel.interfaces.api.auth.SessionAuthentication401",
    ],
    "EXCEPTION_HANDLER": "shared_kernel.interfaces.api.exceptions.exception_handler",
    "DEFAULT_THROTTLE_RATES": {
        "login": "20/min",
        "password_reset": "5/min",
        "register": "20/hour",
        "manual_sync": "6/min",
        "reanalyze": "30/min",
        "bulk_analyze": "5/min",
    },
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "shared_kernel.interfaces.api.pagination.StandardPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
}

SPECTACULAR_SETTINGS = {
    "TITLE": "AI Email Management Platform API",
    "DESCRIPTION": "REST API v1 for the AI Email Management Platform.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": r"/api/v1",
    "COMPONENT_SPLIT_REQUEST": True,
    "ENUM_NAME_OVERRIDES": {
        "SyncStatusEnum": ["PENDING", "RUNNING", "COMPLETED", "PARTIAL", "FAILED"],
        "AnalysisStatusEnum": ["PENDING", "RUNNING", "COMPLETED", "FAILED", "SKIPPED"],
        "GmailAccountStatusEnum": ["ACTIVE", "REVOKED", "ERROR", "DISCONNECTED"],
        "PriorityEnum": ["CRITICAL", "HIGH", "NORMAL", "LOW"],
        "CategoryEnum": ["WORK", "PERSONAL", "FINANCE", "CUSTOMER", "SALES", "MARKETING", "SOCIAL",
                         "NOTIFICATION", "TRANSACTION", "SUPPORT", "NEWSLETTER", "OTHER"],
        "SyncTypeEnum": ["INITIAL", "INCREMENTAL"],
    },
}

# --- Redis / Celery ---
REDIS_URL = env("REDIS_URL", "redis://localhost:6379/0")
CELERY_BROKER_URL = env("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", REDIS_URL)
CELERY_TASK_DEFAULT_QUEUE = "default"
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = "UTC"
CELERY_TASK_ALWAYS_EAGER = False
SYNC_DISPATCH_INTERVAL = env_int("SYNC_DISPATCH_INTERVAL", 60)

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
    }
}

# --- Google OAuth / Gmail ---
GOOGLE_OAUTH_CLIENT_ID = env("GOOGLE_OAUTH_CLIENT_ID", "")
GOOGLE_OAUTH_CLIENT_SECRET = env("GOOGLE_OAUTH_CLIENT_SECRET", "")
GOOGLE_OAUTH_REDIRECT_URI = env(
    "GOOGLE_OAUTH_REDIRECT_URI", "http://localhost:5173/api/v1/integrations/gmail/callback"
)
GMAIL_SCOPES = env("GMAIL_SCOPES", "openid email https://www.googleapis.com/auth/gmail.readonly").split()
GMAIL_INITIAL_SYNC_DAYS = env_int("GMAIL_INITIAL_SYNC_DAYS", 30)
GMAIL_SYNC_INTERVAL_SECONDS = env_int("GMAIL_SYNC_INTERVAL_SECONDS", 300)
GMAIL_GATEWAY = env("GMAIL_GATEWAY", "fake")  # google | fake
# Demo realism: per-message delay in the fake gateway so sync progress is visible in the UI.
FAKE_GMAIL_LATENCY_MS = env_int("FAKE_GMAIL_LATENCY_MS", 120)
INITIAL_SYNC_START_DELAY_SECONDS = env_int("INITIAL_SYNC_START_DELAY_SECONDS", 2)

# --- AI ---
AI_PROVIDER = env("AI_PROVIDER", "fake")  # jev_ai | openrouter | fake
# Queue analysis automatically when sync imports an email. Off for now: analysis only runs
# from the "Analyze with …" button / reanalyze_emails command.
AUTO_ANALYZE_ON_IMPORT = env_bool("AUTO_ANALYZE_ON_IMPORT", False)
# JEV_API_KEY is the name used in the Jev AI docs; JEV_AI_API_KEY (PRD §34) takes precedence.
JEV_AI_API_KEY = env("JEV_AI_API_KEY", env("JEV_API_KEY", ""))
# Full System One endpoint (https://thejevai.com/docs#quickstart)
JEV_AI_BASE_URL = env("JEV_AI_BASE_URL", "https://thejevai.com/v1/systemone")
JEV_AI_MODEL = env("JEV_AI_MODEL", "jev-latest")
# Jev through OpenRouter (AI_PROVIDER=openrouter): same System One contract, OpenRouter key/billing.
# https://openrouter.ai/docs/guides/community/jev
OPENROUTER_API_KEY = env("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = env("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1/systemone")
OPENROUTER_MODEL = env("OPENROUTER_MODEL", "~typesafe/jev-latest")
AI_PROMPT_VERSION = env("AI_PROMPT_VERSION", "v1")
AI_MAX_INPUT_CHARS = env_int("AI_MAX_INPUT_CHARS", 12000)
AI_MAX_OUTPUT_TOKENS = env_int("AI_MAX_OUTPUT_TOKENS", 300)
AI_REQUEST_TIMEOUT_SECONDS = env_int("AI_REQUEST_TIMEOUT_SECONDS", 30)
# Demo realism: simulated classifier latency so "Analyzing" is visible in the UI.
FAKE_AI_LATENCY_MS = env_int("FAKE_AI_LATENCY_MS", 400)

# --- Product thresholds (read at request time via django.conf.settings) ---
SPAM_THRESHOLD_PERCENT = env_int("SPAM_THRESHOLD_PERCENT", 70)
URGENCY_THRESHOLD_PERCENT = env_int("URGENCY_THRESHOLD_PERCENT", 70)

# --- Token encryption (comma-separated Fernet keys; first encrypts, all decrypt) ---
TOKEN_ENCRYPTION_KEYS = env_list("TOKEN_ENCRYPTION_KEY", "")

# --- Email ---
EMAIL_BACKEND = env("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", "localhost")
EMAIL_PORT = env_int("EMAIL_PORT", 25)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", False)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "no-reply@example.com")

# --- Logging ---
LOG_LEVEL = env("LOG_LEVEL", "INFO")
LOG_JSON = env_bool("LOG_JSON", False)
SENTRY_DSN = env("SENTRY_DSN", "")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "plain": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"},
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
            "rename_fields": {"asctime": "time", "levelname": "level", "name": "logger"},
        },
    },
    "filters": {
        "sensitive": {"()": "shared_kernel.infrastructure.logging.SensitiveDataFilter"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json" if LOG_JSON else "plain",
            "filters": ["sensitive"],
        }
    },
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {
        # Route Django's dev-server/request logs through the same JSON + redaction pipeline.
        "django.server": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "django.request": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "celery": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}

# Let Django's LOGGING (JSON + redaction) apply inside Celery workers too.
CELERY_WORKER_HIJACK_ROOT_LOGGER = False
CELERY_WORKER_REDIRECT_STDOUTS = False
