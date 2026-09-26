from __future__ import annotations

import logging
import secrets
from urllib.parse import urlencode

from django.conf import settings
from django.http import Http404, HttpResponse, HttpResponseRedirect
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from gmail_integration.application.ports import GmailError
from gmail_integration.application.use_cases import SyncAlreadyRunning, SyncNotAllowed
from gmail_integration.infrastructure import container
from shared_kernel.domain import NotFoundError
from shared_kernel.interfaces.api.pagination import StandardPagination

from . import serializers as s
from .fake_consent import render_consent

logger = logging.getLogger(__name__)
STATE_KEY = "gmail_oauth_state"


def _spa(path: str, **params) -> HttpResponseRedirect:
    q = f"?{urlencode(params)}" if params else ""
    return HttpResponseRedirect(f"{settings.FRONTEND_URL.rstrip('/')}{path}{q}")


def _demo() -> bool:
    return settings.GMAIL_GATEWAY == "fake"


def _connection_payload(user_id: int) -> dict:
    views = container.get_connection()(user_id=user_id)
    active = [v for v in views if v.status != "DISCONNECTED"]
    account = active[0] if active else None
    return {"connected": bool(account and account.status in ("ACTIVE", "ERROR")),
            "account": account, "demo_mode": _demo()}


class GmailConnectView(APIView):
    """GET /integrations/gmail/connect — browser navigation; redirects to Google (with state)."""

    permission_classes = [AllowAny]

    @extend_schema(responses={302: OpenApiResponse(description="Redirect to Google OAuth")})
    def get(self, request):
        if not request.user.is_authenticated:
            return _spa("/login", next="/integrations")
        url, state = container.start_connection()()
        request.session[STATE_KEY] = state
        return HttpResponseRedirect(url)


class GmailCallbackView(APIView):
    """GET /integrations/gmail/callback — validates `state`, stores credentials server-side."""

    permission_classes = [AllowAny]

    @extend_schema(responses={302: OpenApiResponse(description="Redirect back to the SPA")})
    def get(self, request):
        if not request.user.is_authenticated:
            return _spa("/login", next="/integrations")
        expected = request.session.pop(STATE_KEY, None)
        state = request.query_params.get("state", "")
        if not expected or not state or not secrets.compare_digest(expected, state):
            logger.warning("gmail oauth state mismatch", extra={"user_id": request.user.id})
            return _spa("/integrations", gmail="error", reason="state_mismatch")
        if request.query_params.get("error"):
            return _spa("/integrations", gmail="denied")
        code = request.query_params.get("code")
        if not code:
            return _spa("/integrations", gmail="error", reason="missing_code")
        try:
            container.complete_connection()(user_id=request.user.id, code=code)
        except GmailError:
            logger.warning("gmail oauth code exchange failed", extra={"user_id": request.user.id})
            return _spa("/integrations", gmail="error", reason="exchange_failed")
        return _spa("/integrations", gmail="connected")


class FakeConsentView(APIView):
    """Demo-mode only: simulated Google consent screen."""

    permission_classes = [AllowAny]

    @extend_schema(exclude=True)
    def get(self, request):
        if not _demo():
            raise Http404
        if not request.user.is_authenticated:
            return _spa("/login", next="/integrations")
        from gmail_integration.infrastructure.gmail.fake_gateway import make_fake_code
        from gmail_integration.infrastructure.persistence.models import GmailAccountModel

        existing = GmailAccountModel.objects.filter(user=request.user).order_by("id").first()
        if existing:
            gid, email = existing.google_account_id, existing.email
        else:
            gid = f"fake-u{request.user.id}"
            email = f"{request.user.email.split('@')[0]}@gmail.com"
        html = render_consent(email=email, state=request.query_params.get("state", ""),
                              code=make_fake_code(gid, email),
                              callback_url=f"{settings.APP_URL}/api/v1/integrations/gmail/callback")
        resp = HttpResponse(html)
        resp["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'; form-action 'none'"
        return resp


class GmailConnectionView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=s.GmailConnectionSerializer)
    def get(self, request):
        return Response(s.GmailConnectionSerializer(_connection_payload(request.user.id)).data)


class GmailAccountDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={204: None})
    def delete(self, request, account_id: int):
        container.disconnect()(user_id=request.user.id, account_id=account_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class GmailSyncView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "manual_sync"

    @extend_schema(request=None, responses={202: s.SyncSerializer})
    def post(self, request, account_id: int):
        from gmail_integration.application.use_cases import sync_view

        try:
            sync = container.request_sync()(account_id=account_id, user_id=request.user.id)
        except SyncAlreadyRunning as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        except SyncNotAllowed as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(s.SyncSerializer(sync_view(sync)).data, status=status.HTTP_202_ACCEPTED)


class GmailSyncListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=s.SyncSerializer(many=True))
    def get(self, request, account_id: int):
        syncs = container.list_syncs()(user_id=request.user.id, account_id=account_id, limit=200)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(syncs, request, view=self)
        return paginator.get_paginated_response(s.SyncSerializer(page, many=True).data)


# --- demo controls (fake gateway only) ------------------------------------------------------
class DemoStatusView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(responses=s.DemoStatusSerializer)
    def get(self, request):
        return Response({"demo_mode": _demo() or settings.AI_PROVIDER == "fake",
                         "gmail_gateway": settings.GMAIL_GATEWAY,
                         "ai_provider": settings.AI_PROVIDER})


class _DemoGmailView(APIView):
    permission_classes = [IsAuthenticated]

    def _mailbox(self, request, account_id: int):
        if not _demo():
            raise Http404
        from gmail_integration.infrastructure.persistence.models import (
            FakeMailboxModel,
            GmailAccountModel,
        )

        account = GmailAccountModel.objects.filter(pk=account_id, user=request.user).first()
        if account is None:
            raise NotFoundError("gmail account not found")
        box = FakeMailboxModel.objects.filter(google_account_id=account.google_account_id).first()
        if box is None:
            raise NotFoundError("fake mailbox not found")
        return box


class DemoNewMessagesView(_DemoGmailView):
    @extend_schema(request=None, responses=s.DemoStatusSerializer)
    def post(self, request, account_id: int):
        from django.utils import timezone

        box = self._mailbox(request, account_id)
        box.batch_times = [*box.batch_times, timezone.now().isoformat()]
        box.save(update_fields=["batch_times", "updated_at"])
        return Response({"detail": "3 new messages arrived in the demo Gmail mailbox.",
                         "batches": len(box.batch_times)})


class DemoRevokeView(_DemoGmailView):
    @extend_schema(request=None, responses=s.DemoStatusSerializer)
    def post(self, request, account_id: int):
        box = self._mailbox(request, account_id)
        box.revoked = True
        box.save(update_fields=["revoked", "updated_at"])
        return Response({"detail": "Authorization revoked at the (fake) Google side. "
                                   "The next sync will detect it."})


class DemoRateLimitView(_DemoGmailView):
    @extend_schema(request=None, responses=s.DemoStatusSerializer)
    def post(self, request, account_id: int):
        box = self._mailbox(request, account_id)
        box.rate_limit_failures = 2
        box.save(update_fields=["rate_limit_failures", "updated_at"])
        return Response({"detail": "The next 2 Gmail API calls will return HTTP 429."})
