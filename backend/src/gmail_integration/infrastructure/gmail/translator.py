"""Anti-corruption layer: provider payloads → provider-neutral Mailbox ImportEmail commands."""

from __future__ import annotations

from gmail_integration.application.dto import ImportableMessage
from mailbox_context.application.facade import ImportEmailCommand

PROVIDER = "gmail"


def to_import_command(msg: ImportableMessage, *, user_id: int, account_id: int) -> ImportEmailCommand:
    return ImportEmailCommand(
        user_id=user_id,
        mail_account_id=account_id,
        provider=PROVIDER,
        external_message_id=msg.external_message_id,
        external_thread_id=msg.external_thread_id,
        sender_name=msg.sender_name,
        sender_email=msg.sender_email,
        subject=msg.subject,
        received_at=msg.received_at,
        body_text=msg.body_text,
        body_html=msg.body_html,
        snippet=msg.snippet,
        is_read=msg.is_read,
        recipients=list(msg.recipients),
        labels=list(msg.labels),
        attachments=list(msg.attachments),
    )
