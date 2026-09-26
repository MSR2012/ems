from .base import *  # noqa: F401,F403
from .base import env_bool

DEBUG = False
SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", True)
CSRF_COOKIE_SECURE = env_bool("CSRF_COOKIE_SECURE", True)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_CONTENT_TYPE_NOSNIFF = True
LOG_JSON = True
LOGGING["handlers"]["console"]["formatter"] = "json"  # noqa: F405
