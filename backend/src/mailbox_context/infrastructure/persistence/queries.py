"""Django query services for inbox/detail/thread read models (select_related + annotations,
constant number of SQL queries regardless of page size)."""

from __future__ import annotations

import re

from django.contrib.postgres.search import SearchQuery
from django.core.paginator import EmptyPage, Paginator
from django.db.models import Count, Exists, F, OuterRef, Prefetch, Q, Subquery
from django.db.models.functions import Coalesce

from mailbox_context.application.queries.dto import (
    AnalysisSummary,
    AttachmentDTO,
    EmailDetail,
    InboxFilters,
    InboxItem,
    InboxPage,
    ThreadDetail,
    ThreadMessage,
    Thresholds,
)

from .models import CurrentAnalysisReadModel, EmailAttachmentModel, EmailLabelModel, EmailModel

_TOKEN = re.compile(r"\w+", re.UNICODE)


def search_filter(q: str) -> Q | None:
    """Prefix full-text search over sender/subject/body (tsquery built from safe word tokens)."""
    if not (q or "").strip():
        return None
    tokens = _TOKEN.findall(q)[:8]
    if not tokens:
        return Q(pk__in=[])  # only punctuation: matches nothing
    raw = " & ".join(f"{t}:*" for t in tokens)
    return (Q(search_vector=SearchQuery(raw, search_type="raw", config="english"))
            | Q(search_vector=SearchQuery(raw, search_type="raw", config="simple")))


def analysis_summary(a: CurrentAnalysisReadModel | None, t: Thresholds) -> AnalysisSummary | None:
    if a is None:
        return None
    return AnalysisSummary(
        status=a.status, priority=a.priority, priority_confidence=a.priority_confidence,
        spam_likelihood=a.spam_likelihood, reply_urgency=a.reply_urgency, category=a.category,
        sentiment=a.sentiment, model=a.model, prompt_version=a.prompt_version,
        analyzed_at=a.analyzed_at, error=a.error or None, latest_status=a.latest_status or a.status,
        is_potential_spam=a.spam_likelihood is not None and a.spam_likelihood >= t.spam,
        is_high_urgency=a.reply_urgency is not None and a.reply_urgency >= t.urgency,
        model_version=a.model_version,
    )


def _current(m: EmailModel) -> CurrentAnalysisReadModel | None:
    try:
        return m.current_analysis
    except CurrentAnalysisReadModel.DoesNotExist:
        return None


def apply_filters(qs, f: InboxFilters, t: Thresholds):
    if (sq := search_filter(f.q)) is not None:
        qs = qs.filter(sq)
    if f.priorities:
        qs = qs.filter(current_analysis__priority__in=f.priorities)
    if f.categories:
        qs = qs.filter(current_analysis__category__in=f.categories)
    if f.spam_min is not None:
        qs = qs.filter(current_analysis__spam_likelihood__gte=f.spam_min)
    if f.spam_max is not None:
        qs = qs.filter(current_analysis__spam_likelihood__lte=f.spam_max)
    if f.urgency_min is not None:
        qs = qs.filter(current_analysis__reply_urgency__gte=f.urgency_min)
    if f.urgency_max is not None:
        qs = qs.filter(current_analysis__reply_urgency__lte=f.urgency_max)
    if f.hide_potential_spam:
        qs = qs.filter(Q(current_analysis__spam_likelihood__lt=t.spam)
                       | Q(current_analysis__spam_likelihood__isnull=True))
    if f.is_read is not None:
        qs = qs.filter(is_read=f.is_read)
    if f.received_from is not None:
        qs = qs.filter(received_at__gte=f.received_from)
    if f.received_to is not None:
        qs = qs.filter(received_at__lte=f.received_to)
    return qs


class DjangoInboxQueryService:
    def list_inbox(self, user_id: int, filters: InboxFilters, thresholds: Thresholds,
                   page: int, page_size: int) -> InboxPage:
        thread_size = (EmailModel.objects.filter(user_id=OuterRef("user_id"),
                                                 mail_account_id=OuterRef("mail_account_id"),
                                                 external_thread_id=OuterRef("external_thread_id"))
                       .order_by().values("external_thread_id").annotate(c=Count("id")).values("c"))
        qs = (EmailModel.objects.filter(user_id=user_id)
              .select_related("current_analysis")
              .annotate(has_attachments=Exists(EmailAttachmentModel.objects.filter(email=OuterRef("pk"))),
                        thread_count=Coalesce(Subquery(thread_size), 1))
              .only("id", "external_thread_id", "sender_name", "sender_email", "subject", "snippet",
                    "received_at", "is_read", "user_id", "mail_account_id",
                    *[f"current_analysis__{f.name}" for f in CurrentAnalysisReadModel._meta.fields
                      if f.name != "email"]))
        qs = apply_filters(qs, filters, thresholds).order_by("-received_at", "-id")
        paginator = Paginator(qs, page_size)
        count = paginator.count
        try:
            rows = list(paginator.page(page).object_list) if count else []
        except EmptyPage:
            rows = []
        return InboxPage(count=count, page=page, page_size=page_size, results=[
            InboxItem(id=m.pk, thread_id=m.external_thread_id, sender_name=m.sender_name,
                      sender_email=m.sender_email, subject=m.subject, snippet=m.snippet,
                      received_at=m.received_at, is_read=m.is_read,
                      has_attachments=m.has_attachments, thread_count=m.thread_count,
                      analysis=analysis_summary(_current(m), thresholds))
            for m in rows])

    def _detail_qs(self, user_id: int):
        return (EmailModel.objects.filter(user_id=user_id).select_related("current_analysis")
                .prefetch_related(Prefetch("labels", queryset=EmailLabelModel.objects.order_by("id")),
                                  Prefetch("attachments",
                                           queryset=EmailAttachmentModel.objects.order_by("id"))))

    def _to_detail(self, m: EmailModel, t: Thresholds, thread: list[ThreadMessage]) -> EmailDetail:
        return EmailDetail(
            id=m.pk, provider=m.provider, external_message_id=m.external_message_id,
            thread_id=m.external_thread_id, sender_name=m.sender_name, sender_email=m.sender_email,
            recipients=list(m.recipients or []), subject=m.subject, body_text=m.body_text,
            body_html_sanitized=m.body_html_sanitized, snippet=m.snippet,
            received_at=m.received_at, is_read=m.is_read,
            labels=[lbl.name for lbl in m.labels.all() if lbl.external_label_id != "UNREAD"],
            attachments=[AttachmentDTO(id=a.pk, filename=a.filename, mime_type=a.mime_type, size=a.size)
                         for a in m.attachments.all()],
            analysis=analysis_summary(_current(m), t), thread=thread)

    def _thread_messages(self, user_id: int, m: EmailModel) -> list[ThreadMessage]:
        if not m.external_thread_id:
            return []
        rows = (EmailModel.objects.filter(user_id=user_id, mail_account_id=m.mail_account_id,
                                          external_thread_id=m.external_thread_id)
                .order_by("received_at", "id")
                .values("id", "sender_name", "sender_email", "subject", "snippet", "received_at", "is_read"))
        return [ThreadMessage(**r) for r in rows]

    def email_detail(self, user_id: int, email_id: int, thresholds: Thresholds) -> EmailDetail | None:
        m = self._detail_qs(user_id).filter(pk=email_id).first()
        if m is None:
            return None
        return self._to_detail(m, thresholds, self._thread_messages(user_id, m))

    def thread(self, user_id: int, thread_id: str, thresholds: Thresholds) -> ThreadDetail | None:
        rows = list(self._detail_qs(user_id).filter(external_thread_id=thread_id)
                    .order_by("received_at", "id")[:100])
        if not rows:
            return None
        return ThreadDetail(thread_id=thread_id, subject=rows[0].subject,
                            messages=[self._to_detail(m, thresholds, []) for m in rows])


__all__ = ["DjangoInboxQueryService", "F"]


class DjangoDashboardQueryService:
    """One aggregate query for all counts (conditional COUNTs over emails ⟕ current analysis)."""

    def counts(self, user_id: int, t: Thresholds):
        from mailbox_context.application.queries.dashboard import AnalysisProgress, DashboardCounts

        ca = "current_analysis__"
        # Mutually exclusive progress buckets: anything with a (re-)analysis in flight — or no
        # analysis row yet — counts as in progress only.
        in_flight = (Q(**{f"{ca}status__in": ["PENDING", "RUNNING"]})
                     | Q(**{f"{ca}latest_status__in": ["PENDING", "RUNNING"]})
                     | Q(**{f"{ca}email__isnull": True}))
        agg = EmailModel.objects.filter(user_id=user_id).aggregate(
            total=Count("id"),
            unread=Count("id", filter=Q(is_read=False)),
            high_priority=Count("id", filter=Q(**{f"{ca}status": "COMPLETED",
                                                  f"{ca}priority__in": ["CRITICAL", "HIGH"]})),
            high_urgency=Count("id", filter=Q(**{f"{ca}status": "COMPLETED",
                                                 f"{ca}reply_urgency__gte": t.urgency})),
            potential_spam=Count("id", filter=Q(**{f"{ca}status": "COMPLETED",
                                                   f"{ca}spam_likelihood__gte": t.spam})),
            analyzed=Count("id", filter=Q(**{f"{ca}status": "COMPLETED"}) & ~in_flight),
            in_progress=Count("id", filter=in_flight),
            failed=Count("id", filter=Q(**{f"{ca}status": "FAILED"}) & ~in_flight),
            skipped=Count("id", filter=Q(**{f"{ca}status": "SKIPPED"}) & ~in_flight),
        )
        return (DashboardCounts(total=agg["total"], unread=agg["unread"],
                                high_priority=agg["high_priority"], high_urgency=agg["high_urgency"],
                                potential_spam=agg["potential_spam"]),
                AnalysisProgress(analyzed=agg["analyzed"], in_progress=agg["in_progress"],
                                 failed=agg["failed"], skipped=agg["skipped"]))

    def recent(self, user_id: int, t: Thresholds, limit: int):
        from mailbox_context.application.queries.dto import InboxFilters

        return DjangoInboxQueryService().list_inbox(user_id, InboxFilters(), t, 1, limit).results
