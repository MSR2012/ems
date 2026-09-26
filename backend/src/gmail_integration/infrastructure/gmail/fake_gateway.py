"""Demo-mode Gmail gateway: deterministic mailbox, fake OAuth, and failure simulation.

State lives in FakeMailboxModel so the api and worker processes share it:
- `batch_times`   → new mail appears on later syncs (POST /demo/gmail/{id}/new-messages)
- `revoked`       → every call raises GmailAuthError (POST /demo/gmail/{id}/revoke)
- `rate_limit_failures` → the next N API calls raise GmailRateLimitError
"""

from __future__ import annotations

import secrets
import time
from datetime import datetime, timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.core import signing
from django.db.models import F
from django.utils import timezone

from gmail_integration.application.dto import (
    GmailIdentity,
    GmailMessagePage,
    HistoryPage,
    ImportableMessage,
    TokenGrant,
)
from gmail_integration.application.ports import (
    AccessContext,
    GmailAuthError,
    GmailRateLimitError,
    HistoryExpiredError,
)
from gmail_integration.infrastructure.persistence.models import FakeMailboxModel

from . import fake_dataset

CODE_SALT = "fake-gmail-oauth-code"
PAGE_SIZE = 20


def make_fake_code(google_account_id: str, email: str) -> str:
    return signing.dumps({"gid": google_account_id, "email": email}, salt=CODE_SALT)


def ensure_mailbox(google_account_id: str, email: str) -> FakeMailboxModel:
    box, created = FakeMailboxModel.objects.get_or_create(
        google_account_id=google_account_id, defaults={"email": email, "anchor_at": timezone.now()})
    if not created and box.revoked:
        box.revoked = False  # re-consenting restores authorization
        box.save(update_fields=["revoked", "updated_at"])
    return box


class FakeGmailGateway:
    def __init__(self, latency_ms: int | None = None) -> None:
        self._latency = (latency_ms if latency_ms is not None
                         else getattr(settings, "FAKE_GMAIL_LATENCY_MS", 0)) / 1000

    # --- OAuth ---------------------------------------------------------------------------
    def authorization_url(self, state: str) -> str:
        return f"{settings.APP_URL}/api/v1/integrations/gmail/fake-consent?{urlencode({'state': state})}"

    def exchange_code(self, code: str) -> TokenGrant:
        try:
            data = signing.loads(code, salt=CODE_SALT, max_age=600)
        except signing.BadSignature as exc:
            raise GmailAuthError("invalid authorization code") from exc
        ensure_mailbox(data["gid"], data["email"])
        return TokenGrant(access_token=f"fake-at-{data['gid']}|{secrets.token_urlsafe(16)}",
                          refresh_token=f"fake-rt-{data['gid']}|{secrets.token_urlsafe(16)}",
                          expires_at=timezone.now() + timedelta(hours=1),
                          scopes=tuple(settings.GMAIL_SCOPES))

    def fetch_identity(self, grant: TokenGrant) -> GmailIdentity:
        gid = grant.access_token.removeprefix("fake-at-").split("|", 1)[0]
        box = FakeMailboxModel.objects.get(google_account_id=gid)
        return GmailIdentity(google_account_id=gid, email=box.email)

    def refresh(self, ctx: AccessContext) -> TokenGrant:
        self._box(ctx)  # raises if revoked
        return TokenGrant(access_token=f"fake-at-{ctx.google_account_id}|{secrets.token_urlsafe(16)}",
                          expires_at=timezone.now() + timedelta(hours=1))

    def revoke(self, ctx: AccessContext) -> None:
        return None

    # --- mailbox -------------------------------------------------------------------------
    def _box(self, ctx: AccessContext, *, api_call: bool = True) -> FakeMailboxModel:
        box = FakeMailboxModel.objects.filter(google_account_id=ctx.google_account_id).first()
        if box is None or box.revoked:
            raise GmailAuthError("invalid_grant: Token has been expired or revoked.")
        if api_call and box.rate_limit_failures > 0:
            FakeMailboxModel.objects.filter(pk=box.pk, rate_limit_failures__gt=0).update(
                rate_limit_failures=F("rate_limit_failures") - 1)
            raise GmailRateLimitError("Gmail API rate limit exceeded (userRateLimitExceeded)",
                                      retry_after=2)
        return box

    def _snapshot(self, box: FakeMailboxModel) -> fake_dataset.MailboxSnapshot:
        times = [datetime.fromisoformat(t) for t in box.batch_times]
        return fake_dataset.snapshot(box.anchor_at, times)

    def current_history_id(self, ctx: AccessContext) -> str:
        return str(self._snapshot(self._box(ctx)).history_id)

    def list_recent_message_ids(self, ctx: AccessContext, *, days: int,
                                page_token: str | None = None) -> GmailMessagePage:
        snap = self._snapshot(self._box(ctx))
        cutoff = timezone.now() - timedelta(days=days)
        entries = sorted((e for e in snap.entries if e.received_at >= cutoff),
                         key=lambda e: e.received_at, reverse=True)
        offset = int(page_token or 0)
        page = entries[offset:offset + PAGE_SIZE]
        nxt = str(offset + PAGE_SIZE) if offset + PAGE_SIZE < len(entries) else None
        return GmailMessagePage(message_ids=[f"fake-{e.message.key}" for e in page],
                                next_page_token=nxt)

    def list_history(self, ctx: AccessContext, *, start_history_id: str,
                     page_token: str | None = None) -> HistoryPage:
        snap = self._snapshot(self._box(ctx))
        start = int(start_history_id)
        if start < 1000:
            raise HistoryExpiredError("history id too old")
        added = [f"fake-{e.message.key}" for e in sorted(snap.entries, key=lambda e: e.history_id)
                 if e.history_id > start]
        return HistoryPage(added_message_ids=added, history_id=str(snap.history_id))

    def get_message(self, ctx: AccessContext, message_id: str) -> ImportableMessage:
        box = self._box(ctx)
        if self._latency:
            time.sleep(self._latency)
        entry = self._snapshot(box).by_key().get(message_id.removeprefix("fake-"))
        if entry is None:
            raise KeyError(message_id)
        return fake_dataset.to_importable(entry)
