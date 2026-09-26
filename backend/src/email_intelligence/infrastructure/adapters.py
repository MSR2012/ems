from __future__ import annotations

from email_intelligence.application.ports import EmailContent
from mailbox_context.application import facade


class MailboxContentProvider:
    """EmailContentProvider backed by the Mailbox context's published application API."""

    def get_content(self, email_id: int) -> EmailContent | None:
        c = facade.content_query().get_content(email_id)
        if c is None:
            return None
        return EmailContent(email_id=c.email_id, user_id=c.user_id, sender_email=c.sender_email,
                            sender_name=c.sender_name, subject=c.subject, body_text=c.body_text)


class CeleryAnalysisQueue:
    def enqueue_analysis(self, analysis_id: int) -> None:
        from django.db import transaction

        from .tasks import analyze_email

        transaction.on_commit(lambda: analyze_email.delay(analysis_id=analysis_id))


class SqlAttentionCandidates:
    def current_completed(self, user_id, thresholds):
        from email_intelligence.application.needs_attention import AnalysisRow

        from .persistence.queries import attention_candidates

        return [AnalysisRow(**r) for r in attention_candidates(user_id, thresholds.spam.value,
                                                              thresholds.urgency.value)]


class MailboxEmailSummaries:
    def summaries(self, user_id, email_ids):
        from email_intelligence.application.needs_attention import EmailSummary

        return [EmailSummary(id=s.id, sender_name=s.sender_name, sender_email=s.sender_email,
                             subject=s.subject, snippet=s.snippet, received_at=s.received_at,
                             is_read=s.is_read)
                for s in facade.content_query().get_summaries(user_id, email_ids)]
