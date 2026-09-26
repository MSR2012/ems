from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework.authentication import SessionAuthentication


class SessionAuthentication401(SessionAuthentication):
    """Session auth that makes DRF answer 401 (not 403) for anonymous requests."""

    def authenticate_header(self, request) -> str:
        return 'Session realm="api"'


def enforce_csrf(view_cls):
    """Enforce Django CSRF on public (anonymous) unsafe endpoints too — DRF's
    SessionAuthentication only checks CSRF for already-authenticated users."""
    return method_decorator(csrf_protect, name="dispatch")(view_cls)


try:  # document the session scheme in the OpenAPI schema
    from drf_spectacular.extensions import OpenApiAuthenticationExtension

    class SessionAuthentication401Scheme(OpenApiAuthenticationExtension):
        target_class = "shared_kernel.interfaces.api.auth.SessionAuthentication401"
        name = "sessionAuth"

        def get_security_definition(self, auto_schema):
            return {"type": "apiKey", "in": "cookie", "name": "sessionid"}
except ImportError:  # pragma: no cover
    pass
