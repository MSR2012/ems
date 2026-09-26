from __future__ import annotations

from mailbox_context.application.facade import EmailContentDTO, EmailSummaryDTO

from .persistence.models import EmailModel


class DjangoEmailContentQuery:
    def get_content(self, email_id: int) -> EmailContentDTO | None:
        m = (EmailModel.objects.filter(pk=email_id)
             .only("id", "user_id", "sender_name", "sender_email", "subject", "body_text",
                   "received_at").first())
        if m is None:
            return None
        return EmailContentDTO(email_id=m.pk, user_id=m.user_id, sender_name=m.sender_name,
                               sender_email=m.sender_email, subject=m.subject,
                               body_text=m.body_text, received_at=m.received_at,
                               has_attachments=m.attachments.exists())

    def get_summaries(self, user_id: int, email_ids: list[int]) -> list[EmailSummaryDTO]:
        qs = EmailModel.objects.filter(user_id=user_id, pk__in=email_ids).only(
            "id", "sender_name", "sender_email", "subject", "snippet", "received_at", "is_read",
            "external_thread_id")
        return [EmailSummaryDTO(id=m.pk, sender_name=m.sender_name, sender_email=m.sender_email,
                                subject=m.subject, snippet=m.snippet, received_at=m.received_at,
                                is_read=m.is_read, external_thread_id=m.external_thread_id)
                for m in qs]

    def email_ids_for_user(self, user_id: int) -> list[int]:
        return list(EmailModel.objects.filter(user_id=user_id).order_by("-received_at")
                    .values_list("id", flat=True))

    def owned_email_ids(self, user_id: int, email_ids: list[int]) -> set[int]:
        return set(EmailModel.objects.filter(user_id=user_id, pk__in=email_ids)
                   .values_list("id", flat=True))
