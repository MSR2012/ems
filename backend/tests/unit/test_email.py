from datetime import UTC, datetime

import pytest

from mailbox_context.domain.email import Email, EmailAttachment, EmailLabel
from mailbox_context.domain.events import EmailImported
from mailbox_context.domain.value_objects import EmailAddress, ProviderMessageRef
from shared_kernel.domain import InvariantViolation, UserId


def make(**kw):
    return Email(
        user_id=UserId(1),
        ref=ProviderMessageRef("gmail", 5, kw.get("mid", "m1"), "t1"),
        sender=EmailAddress("Alice@Example.com", " Alice "),
        subject=kw.get("subject", "Hello"),
        body_text=kw.get("body", "Hi there,   how are you?"),
        received_at=datetime(2026, 9, 1, tzinfo=UTC),
    )


def test_email_address_is_normalized():
    a = EmailAddress("Alice@Example.COM", " Alice ")
    assert a.email == "alice@example.com" and a.name == "Alice" and a.display == "Alice"
    with pytest.raises(InvariantViolation):
        EmailAddress("not-an-email")


def test_snippet_is_derived_from_body():
    assert make().snippet == "Hi there, how are you?"


def test_mark_imported_requires_id_and_raises_event():
    e = make()
    with pytest.raises(InvariantViolation):
        e.mark_imported()
    e.id = 7
    e.mark_imported()
    ev = e.pull_events()[0]
    assert isinstance(ev, EmailImported) and ev.email_id == 7 and ev.analyzable


def test_empty_email_is_not_analyzable():
    e = make(subject="", body="  ")
    e.id = 1
    e.mark_imported()
    assert not e.is_analyzable and not e.pull_events()[0].analyzable


def test_sync_provider_state_detects_changes():
    e = make()
    assert e.sync_provider_state(is_read=True, labels=[EmailLabel(external_label_id="INBOX",
                                                                  name="INBOX")])
    assert not e.sync_provider_state(is_read=True, labels=[EmailLabel(external_label_id="INBOX",
                                                                      name="INBOX")])


def test_attachment_size_cannot_be_negative():
    with pytest.raises(InvariantViolation):
        EmailAttachment(external_attachment_id="a", filename="f", mime_type="x", size=-1)


def test_provider_ref_requires_ids():
    with pytest.raises(InvariantViolation):
        ProviderMessageRef("", 1, "m", "t")
