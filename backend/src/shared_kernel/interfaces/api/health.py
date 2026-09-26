"""GET /api/v1/health — database, Redis, and Celery worker checks (public)."""

from __future__ import annotations

import redis
from django.conf import settings
from django.db import connection
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


def _check_database() -> dict:
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
        return {"status": "ok"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "detail": exc.__class__.__name__}


def _check_redis() -> dict:
    try:
        redis.Redis.from_url(settings.REDIS_URL, socket_timeout=2).ping()
        return {"status": "ok"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "detail": exc.__class__.__name__}


def _check_celery() -> dict:
    try:
        from config.celery import app

        replies = app.control.ping(timeout=1.5) or []
        if replies:
            return {"status": "ok", "workers": sorted(k for r in replies for k in r)}
        return {"status": "error", "detail": "no workers responded"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "detail": exc.__class__.__name__}


class HealthView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []

    @extend_schema(responses=inline_serializer("Health", {"status": serializers.CharField(),
                                                          "checks": serializers.DictField()}))
    def get(self, request):
        checks = {"database": _check_database(), "redis": _check_redis(),
                  "celery": _check_celery()}
        healthy = all(c["status"] == "ok" for c in checks.values())
        return Response({"status": "ok" if healthy else "degraded", "checks": checks},
                        status=200 if healthy else 503)
