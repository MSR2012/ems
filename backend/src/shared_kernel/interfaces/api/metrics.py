"""GET /api/v1/ops/metrics — operational metrics (staff only): synced/analyzed messages,
failures and processing durations, aggregated across all users (no content)."""

from __future__ import annotations

from django.db import connection
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

SQL = {
    "emails_total": "SELECT count(*) FROM emails",
    "syncs_by_status": "SELECT status, count(*) FROM email_syncs GROUP BY status",
    "analyses_by_status": "SELECT status, count(*) FROM email_analyses GROUP BY status",
    "ai_calls_by_status": "SELECT status, count(*) FROM ai_usage_logs GROUP BY status",
}


class MetricsView(APIView):
    permission_classes = [IsAdminUser]

    @extend_schema(responses=inline_serializer("OpsMetrics", {"metrics": serializers.DictField()}))
    def get(self, request):
        out: dict = {}
        with connection.cursor() as cur:
            cur.execute(SQL["emails_total"])
            out["emails_total"] = cur.fetchone()[0]
            for key in ("syncs_by_status", "analyses_by_status", "ai_calls_by_status"):
                cur.execute(SQL[key])
                out[key] = dict(cur.fetchall())
            cur.execute("SELECT coalesce(avg(duration_ms),0), coalesce(sum(input_tokens),0), "
                        "coalesce(sum(output_tokens),0) FROM ai_usage_logs")
            avg_ms, tin, tout = cur.fetchone()
            out["ai_avg_duration_ms"] = round(float(avg_ms), 1)
            out["ai_tokens"] = {"input": int(tin), "output": int(tout)}
            cur.execute("SELECT coalesce(avg(extract(epoch FROM completed_at - started_at)), 0) "
                        "FROM email_syncs WHERE status IN ('COMPLETED','PARTIAL')")
            out["sync_avg_duration_s"] = round(float(cur.fetchone()[0]), 2)
        return Response({"metrics": out})
