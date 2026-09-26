"""Test helpers that build demo-mode fixtures through the real code paths."""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from gmail_integration.domain.gmail_account import GmailAccount
from gmail_integration.domain.value_objects import OAuthCredentials
from gmail_integration.infrastructure.gmail.fake_gateway import ensure_mailbox
from gmail_integration.infrastructure.persistence.models import FakeMailboxModel
from gmail_integration.infrastructure.persistence.repositories import DjangoGmailAccountRepository
from shared_kernel.domain import UserId
from shared_kernel.infrastructure.encryption import FernetTokenCipher


def connect_fake_account(user, gid: str | None = None, email: str | None = None,
                         expires_in: timedelta = timedelta(hours=1)) -> GmailAccount:
    gid = gid or f"fake-test-{user.pk}"
    email = email or f"inbox{user.pk}@gmail.com"
    ensure_mailbox(gid, email)
    repo = DjangoGmailAccountRepository(FernetTokenCipher())
    account = GmailAccount.connect(
        user_id=UserId(user.pk), google_account_id=gid, email=email,
        credentials=OAuthCredentials(access_token="fake-at-plain-ACCESS-SECRET",
                                     refresh_token="fake-rt-plain-REFRESH-SECRET",
                                     expires_at=timezone.now() + expires_in),
    )
    repo.save(account)
    return account


def mailbox(account) -> FakeMailboxModel:
    return FakeMailboxModel.objects.get(google_account_id=account.google_account_id)


def deliver_new_mail(account) -> None:
    box = mailbox(account)
    box.batch_times = [*box.batch_times, timezone.now().isoformat()]
    box.save()
