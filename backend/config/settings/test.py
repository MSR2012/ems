from .base import *  # noqa: F401,F403

DEBUG = False
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
CELERY_TASK_ALWAYS_EAGER = True
# False so eager retries chain like a real worker (tests assert on resulting DB state)
CELERY_TASK_EAGER_PROPAGATES = False
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
GMAIL_GATEWAY = "fake"
AI_PROVIDER = "fake"
TOKEN_ENCRYPTION_KEYS = ["QOfTpU-17kxX7Ns7sn1GbPVJSFYxem8YpiOQrovffsA="]
FAKE_GMAIL_LATENCY_MS = 0
INITIAL_SYNC_START_DELAY_SECONDS = 0
FAKE_AI_LATENCY_MS = 0
