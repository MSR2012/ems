from math import ceil

from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from mailbox_context.application.queries.dto import InboxFilters, Thresholds
from mailbox_context.infrastructure import container

from . import serializers as s


def thresholds() -> Thresholds:
    return Thresholds(spam=settings.SPAM_THRESHOLD_PERCENT, urgency=settings.URGENCY_THRESHOLD_PERCENT)


class InboxView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(operation_id="emails_list", parameters=[s.InboxQuerySerializer],
                   responses=s.InboxPageSerializer)
    def get(self, request):
        params = s.InboxQuerySerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        p = params.validated_data
        filters = InboxFilters(
            q=p.get("q", ""), priorities=p.get("priority", ()), categories=p.get("category", ()),
            spam_min=p.get("spam_likelihood_min"), spam_max=p.get("spam_likelihood_max"),
            urgency_min=p.get("reply_urgency_min"), urgency_max=p.get("reply_urgency_max"),
            hide_potential_spam=p.get("hide_potential_spam", False), is_read=p.get("is_read"),
            received_from=p.get("received_from"), received_to=p.get("received_to"))
        t = thresholds()
        page = container.list_inbox()(user_id=request.user.id, filters=filters, thresholds=t,
                                      page=p["page"], page_size=p["page_size"])
        pages = max(1, ceil(page.count / page.page_size))
        data = {
            "count": page.count, "page": page.page, "page_size": page.page_size,
            "next": page.page + 1 if page.page < pages else None,
            "previous": page.page - 1 if page.page > 1 else None,
            "thresholds": {"spam": t.spam, "urgency": t.urgency},
            "results": page.results,
        }
        return Response(s.InboxPageSerializer(data).data)


class EmailDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=s.EmailDetailSerializer)
    def get(self, request, email_id: int):
        detail = container.email_detail()(user_id=request.user.id, email_id=email_id,
                                          thresholds=thresholds())
        return Response(s.EmailDetailSerializer(detail).data)


class ThreadView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=s.ThreadSerializer)
    def get(self, request, thread_id: str):
        detail = container.thread()(user_id=request.user.id, thread_id=thread_id,
                                    thresholds=thresholds())
        return Response(s.ThreadSerializer(detail).data)


class DashboardSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=s.DashboardSummarySerializer)
    def get(self, request):
        t = thresholds()
        summary = container.dashboard_summary()(user_id=request.user.id, thresholds=t)
        data = {"counts": summary.counts, "analysis": summary.analysis, "recent": summary.recent,
                "sync": summary.sync, "thresholds": {"spam": t.spam, "urgency": t.urgency}}
        return Response(s.DashboardSummarySerializer(data).data)
