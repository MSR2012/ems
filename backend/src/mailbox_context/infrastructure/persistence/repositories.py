from __future__ import annotations

from django.db import IntegrityError, transaction
from django.db.models import Prefetch

from mailbox_context.application.ports import DuplicateEmailError
from mailbox_context.domain.email import Email, EmailAttachment, EmailLabel, Recipient
from mailbox_context.domain.value_objects import EmailAddress, ProviderMessageRef
from shared_kernel.domain import UserId

from .models import EmailAttachmentModel, EmailLabelModel, EmailModel


def _recipients_to_json(recipients: list[Recipient]) -> list[dict]:
    return [{"type": r.kind, "email": r.address.email, "name": r.address.name} for r in recipients]


def _recipients_from_json(data: list[dict]) -> list[Recipient]:
    out = []
    for item in data or []:
        try:
            out.append(Recipient(kind=item.get("type", "to"),
                                 address=EmailAddress(item["email"], item.get("name", ""))))
        except Exception:  # noqa: BLE001 - tolerate legacy/malformed recipient rows
            continue
    return out


def to_domain(m: EmailModel) -> Email:
    return Email(
        id=m.pk,
        user_id=UserId(m.user_id),
        ref=ProviderMessageRef(provider=m.provider, mail_account_id=m.mail_account_id,
                               external_message_id=m.external_message_id,
                               external_thread_id=m.external_thread_id),
        sender=EmailAddress(m.sender_email, m.sender_name),
        subject=m.subject,
        received_at=m.received_at,
        recipients=_recipients_from_json(m.recipients),
        body_text=m.body_text,
        body_html_sanitized=m.body_html_sanitized,
        snippet=m.snippet,
        is_read=m.is_read,
        labels=[EmailLabel(id=lbl.pk, external_label_id=lbl.external_label_id, name=lbl.name)
                for lbl in m.labels.all()],
        attachments=[EmailAttachment(id=a.pk, external_attachment_id=a.external_attachment_id,
                                     filename=a.filename, mime_type=a.mime_type, size=a.size)
                     for a in m.attachments.all()],
        created_at=m.created_at,
    )


class DjangoEmailRepository:
    def _qs(self):
        return EmailModel.objects.prefetch_related(
            Prefetch("labels", queryset=EmailLabelModel.objects.order_by("id")),
            Prefetch("attachments", queryset=EmailAttachmentModel.objects.order_by("id")),
        )

    def get(self, email_id: int) -> Email | None:
        m = self._qs().filter(pk=email_id).first()
        return to_domain(m) if m else None

    def get_for_user(self, email_id: int, user_id: int) -> Email | None:
        m = self._qs().filter(pk=email_id, user_id=user_id).first()
        return to_domain(m) if m else None

    def find_by_external_id(self, mail_account_id: int, external_message_id: str) -> Email | None:
        m = self._qs().filter(mail_account_id=mail_account_id,
                              external_message_id=external_message_id).first()
        return to_domain(m) if m else None

    def save(self, email: Email) -> Email:
        fields = dict(
            user_id=int(email.user_id), mail_account_id=email.ref.mail_account_id,
            provider=email.ref.provider, external_message_id=email.ref.external_message_id,
            external_thread_id=email.ref.external_thread_id, sender_name=email.sender.name,
            sender_email=email.sender.email, recipients=_recipients_to_json(email.recipients),
            subject=email.subject, body_text=email.body_text,
            body_html_sanitized=email.body_html_sanitized, snippet=email.snippet,
            received_at=email.received_at, is_read=email.is_read,
        )
        if email.id:
            EmailModel.objects.filter(pk=email.id).update(**fields)
            m_id = email.id
        else:
            try:
                with transaction.atomic():
                    m = EmailModel.objects.create(**fields)
            except IntegrityError as exc:
                raise DuplicateEmailError(email.ref.external_message_id) from exc
            m_id = m.pk
            email.id = m_id
            email.created_at = m.created_at
            EmailAttachmentModel.objects.bulk_create([
                EmailAttachmentModel(email_id=m_id, external_attachment_id=a.external_attachment_id,
                                     filename=a.filename, mime_type=a.mime_type, size=a.size)
                for a in email.attachments
            ])
        EmailLabelModel.objects.filter(email_id=m_id).delete()
        EmailLabelModel.objects.bulk_create([
            EmailLabelModel(email_id=m_id, external_label_id=lbl.external_label_id, name=lbl.name)
            for lbl in {lbl.external_label_id: lbl for lbl in email.labels}.values()
        ])
        return email
