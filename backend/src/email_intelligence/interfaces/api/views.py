from django.conf import settings
from django.http import Http404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from email_intelligence.infrastructure import container

from . import serializers as s


class ReanalyzeView(APIView):
    """POST /emails/{id}/reanalyze — re-queue analysis with the active model/prompt version."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "reanalyze"

    @extend_schema(request=None, responses={202: s.ReanalyzeResponseSerializer})
    def post(self, request, email_id: int):
        # User-initiated: re-run finished analyses and re-enqueue a pending one (the atomic
        # claim in AnalyzeEmail makes a duplicate job harmless).
        a, _ = container.request_analysis().request(email_id=email_id, user_id=request.user.id,
                                                    force=True, requeue_pending=True)
        return Response({"analysis_id": a.id, "status": str(a.status), "model": a.model,
                         "prompt_version": a.prompt_version}, status=status.HTTP_202_ACCEPTED)


class BulkAnalyzeView(APIView):
    """POST /emails/analyze — queue analysis of the user's inbox with the active AI provider.
    Returns 202 immediately; a Celery task on the `analysis` queue fans out per-email jobs."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "bulk_analyze"

    @extend_schema(request=s.BulkAnalyzeRequestSerializer, responses={202: s.BulkAnalyzeResponseSerializer})
    def post(self, request):
        from email_intelligence.infrastructure.ai.config import active_provider
        from email_intelligence.infrastructure.tasks import reanalyze_emails

        data = s.BulkAnalyzeRequestSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        force = data.validated_data["force"]
        reanalyze_emails.delay(user_id=request.user.id, force=force)
        v = container.version()
        return Response({"status": "queued", "provider": active_provider(), "model": v.model,
                         "prompt_version": v.prompt_version, "force": force},
                        status=status.HTTP_202_ACCEPTED)


class DemoAiFailureModeView(APIView):
    permission_classes = [IsAuthenticated]

    def _guard(self):
        if settings.AI_PROVIDER != "fake":
            raise Http404

    @extend_schema(responses=s.FailureModeSerializer)
    def get(self, request):
        self._guard()
        from email_intelligence.infrastructure.ai.fake import get_failure_mode

        return Response({"mode": get_failure_mode()})

    @extend_schema(request=s.FailureModeSerializer, responses=s.FailureModeSerializer)
    def post(self, request):
        self._guard()
        from email_intelligence.infrastructure.ai.fake import set_failure_mode

        data = s.FailureModeSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        set_failure_mode(data.validated_data["mode"])
        return Response({"mode": data.validated_data["mode"]})


class NeedsAttentionView(APIView):
    """GET /dashboard/needs-attention — AI-based suggestion ordered by the AttentionPolicy."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses=s.NeedsAttentionSerializer)
    def get(self, request):
        from email_intelligence.domain.classifications import Thresholds

        try:
            limit = max(1, min(int(request.query_params.get("limit", 10)), 50))
        except ValueError:
            limit = 10
        t = Thresholds.of(settings.SPAM_THRESHOLD_PERCENT, settings.URGENCY_THRESHOLD_PERCENT)
        result = container.needs_attention()(user_id=request.user.id, thresholds=t, limit=limit)
        return Response(s.NeedsAttentionSerializer({
            "description": result.description, "ai_suggestion": True,
            "thresholds": {"spam": t.spam.value, "urgency": t.urgency.value},
            "total": result.total, "results": result.items}).data)
