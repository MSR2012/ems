from django.conf import settings
from django.contrib.auth import login, logout, update_session_auth_hash
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from identity.infrastructure import container
from identity.infrastructure.persistence.models import UserModel
from shared_kernel.interfaces.api.auth import enforce_csrf

from . import serializers as s

PROVIDER_NAMES = {"jev_ai": "Jev AI", "openrouter": "Jev AI (via OpenRouter)"}


def _app_settings() -> dict:
    return {
        "spam_threshold_percent": settings.SPAM_THRESHOLD_PERCENT,
        "urgency_threshold_percent": settings.URGENCY_THRESHOLD_PERCENT,
        "ai_provider": settings.AI_PROVIDER,
        "ai_provider_name": PROVIDER_NAMES.get(settings.AI_PROVIDER, "Jev AI (demo simulator)"),
        "demo_mode": settings.GMAIL_GATEWAY == "fake" or settings.AI_PROVIDER == "fake",
    }


def _me(user) -> dict:
    return {"id": user.id, "email": user.email, "name": user.name, "created_at": user.created_at,
            "settings": _app_settings()}


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(responses=s.MessageSerializer)
    def get(self, request):
        get_token(request)
        return Response({"detail": "CSRF cookie set"})


@enforce_csrf
class RegisterView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "register"

    @extend_schema(request=s.RegisterSerializer, responses={201: s.MeSerializer})
    def post(self, request):
        data = s.RegisterSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        user = container.register_user()(**data.validated_data)
        model = UserModel.objects.get(pk=user.id)
        login(request, model, backend="django.contrib.auth.backends.ModelBackend")
        return Response(_me(model), status=status.HTTP_201_CREATED)


@enforce_csrf
class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    @extend_schema(request=s.LoginSerializer, responses=s.MeSerializer)
    def post(self, request):
        data = s.LoginSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        from identity.application.use_cases import InvalidCredentials

        try:
            user = container.authenticate_user()(**data.validated_data)
        except InvalidCredentials:
            return Response({"detail": "Invalid email or password."},
                            status=status.HTTP_400_BAD_REQUEST)
        model = UserModel.objects.get(pk=user.id)
        login(request, model, backend="django.contrib.auth.backends.ModelBackend")
        return Response(_me(model))


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses={204: None})
    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


@enforce_csrf
class PasswordResetView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset"

    @extend_schema(request=s.PasswordResetSerializer, responses=s.MessageSerializer)
    def post(self, request):
        data = s.PasswordResetSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        container.request_password_reset()(email=data.validated_data["email"])
        return Response({"detail": "If an account exists for that email, a reset link has been sent."})


@enforce_csrf
class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset"

    @extend_schema(request=s.PasswordResetConfirmSerializer, responses=s.MessageSerializer)
    def post(self, request):
        data = s.PasswordResetConfirmSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        container.confirm_password_reset()(**data.validated_data)
        return Response({"detail": "Your password has been reset. You can now sign in."})


class SessionView(APIView):
    """Public: who is signed in (200 either way, so the SPA can bootstrap without an error)."""

    permission_classes = [AllowAny]

    @extend_schema(responses=s.SessionSerializer)
    def get(self, request):
        user = request.user if request.user.is_authenticated else None
        return Response({"authenticated": user is not None, "user": _me(user) if user else None})


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=s.MeSerializer)
    def get(self, request):
        return Response(_me(request.user))

    @extend_schema(request=s.MeSerializer, responses=s.MeSerializer)
    def patch(self, request):
        data = s.MeSerializer(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        container.update_profile()(user_id=request.user.id, name=data.validated_data.get("name"))
        request.user.refresh_from_db()
        return Response(_me(request.user))


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=s.ChangePasswordSerializer, responses=s.MessageSerializer)
    def post(self, request):
        data = s.ChangePasswordSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        container.change_password()(user_id=request.user.id, **data.validated_data)
        request.user.refresh_from_db()
        update_session_auth_hash(request, request.user)
        return Response({"detail": "Password updated."})
