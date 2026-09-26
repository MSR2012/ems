"""Idempotent demo seed: demo user + connected fake Gmail account + realistic mailbox,
analyses across all priorities/categories (plus pending/failed/skipped), and sync history."""

from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from email_intelligence.domain.classifications import (
    AnalysisResult,
    Category,
    Percentage,
    Priority,
    Sentiment,
)
from email_intelligence.domain.email_analysis import EmailAnalysis
from email_intelligence.infrastructure.ai import fake_rules
from email_intelligence.infrastructure.ai.config import active_model, active_prompt_version
from email_intelligence.infrastructure.persistence.models import EmailAnalysisModel
from email_intelligence.infrastructure.persistence.repositories import (
    DjangoEmailAnalysisRepository,
)
from gmail_integration.domain.gmail_account import GmailAccount
from gmail_integration.domain.value_objects import HistoryId, OAuthCredentials
from gmail_integration.infrastructure.gmail import fake_dataset
from gmail_integration.infrastructure.gmail.translator import to_import_command
from gmail_integration.infrastructure.persistence.models import (
    EmailSyncModel,
    FakeMailboxModel,
    GmailAccountModel,
)
from gmail_integration.infrastructure.persistence.repositories import DjangoGmailAccountRepository
from identity.infrastructure.persistence.models import UserModel
from mailbox_context.application import facade
from mailbox_context.infrastructure.persistence.models import EmailModel
from shared_kernel.domain import UserId
from shared_kernel.infrastructure.encryption import FernetTokenCipher
from shared_kernel.infrastructure.event_bus import event_bus

DEMO_EMAIL, DEMO_PASSWORD = "demo@example.com", "DemoPass123!"
OTHER_EMAIL, OTHER_PASSWORD = "other@example.com", "OtherPass123!"

PENDING_KEYS = {"m031", "m032"}
FAILED_KEYS = {"m037": "Invalid AI output: 'priority' must be one of CRITICAL, HIGH, NORMAL, LOW",
               "m038": "AI provider timeout after 3 attempts"}


class Command(BaseCommand):
    help = "Seed demo data (idempotent)."

    def handle(self, *args, **options):
        with event_bus.muted():
            demo = self._user(DEMO_EMAIL, DEMO_PASSWORD, "Demo User")
            demo_account = self._account(demo, "fake-demo", "demo.inbox@gmail.com")
            created = self._import(demo, demo_account, limit=None)
            self._analyses(demo, demo_account)
            self._sync_history(demo_account, created)

            other = self._user(OTHER_EMAIL, OTHER_PASSWORD, "Other User")
            other_account = self._account(other, "fake-other", "other.inbox@gmail.com")
            created_other = self._import(other, other_account, limit=5)
            self._analyses(other, other_account)
            self._sync_history(other_account, created_other)

        counts = {
            "users": UserModel.objects.count(),
            "emails": EmailModel.objects.count(),
            "analyses": EmailAnalysisModel.objects.count(),
            "syncs": EmailSyncModel.objects.count(),
        }
        self.stdout.write(self.style.SUCCESS(f"seed_demo complete: {counts}"))
        self.stdout.write(f"Demo login: {DEMO_EMAIL} (password: see README)")

    # ------------------------------------------------------------------------------------
    def _user(self, email: str, password: str, name: str) -> UserModel:
        user = UserModel.objects.filter(email=email).first()
        if user is None:
            user = UserModel.objects.create_user(email=email, password=password, name=name)
        return user

    def _mailbox(self, google_id: str, email: str) -> FakeMailboxModel:
        box, _ = FakeMailboxModel.objects.get_or_create(
            google_account_id=google_id, defaults={"email": email, "anchor_at": timezone.now()})
        return box

    def _account(self, user: UserModel, google_id: str, email: str) -> GmailAccountModel:
        self._mailbox(google_id, email)
        existing = GmailAccountModel.objects.filter(user=user, google_account_id=google_id).first()
        if existing:
            return existing
        repo = DjangoGmailAccountRepository(FernetTokenCipher())
        now = timezone.now()
        account = GmailAccount.connect(
            user_id=UserId(user.pk), google_account_id=google_id, email=email,
            credentials=OAuthCredentials(access_token=f"fake-access-{google_id}",
                                         refresh_token=f"fake-refresh-{google_id}",
                                         expires_at=now + timedelta(hours=1),
                                         scopes=tuple(settings.GMAIL_SCOPES)),
            now=now)
        account.next_sync_at = now + timedelta(seconds=settings.GMAIL_SYNC_INTERVAL_SECONDS)
        repo.save(account)
        return GmailAccountModel.objects.get(pk=account.id)

    def _import(self, user: UserModel, account: GmailAccountModel, limit: int | None) -> int:
        box = FakeMailboxModel.objects.get(google_account_id=account.google_account_id)
        snap = fake_dataset.snapshot(box.anchor_at, [])
        entries = snap.entries[:limit] if limit else snap.entries
        created = 0
        for entry in entries:
            result = facade.import_email(to_import_command(
                fake_dataset.to_importable(entry), user_id=user.pk, account_id=account.pk))
            created += int(result.created)
        if not account.history_id:
            GmailAccountModel.objects.filter(pk=account.pk).update(
                history_id=str(HistoryId(str(snap.history_id))), last_synced_at=timezone.now())
        return created

    @transaction.atomic
    def _analyses(self, user: UserModel, account: GmailAccountModel) -> None:
        repo = DjangoEmailAnalysisRepository()
        analyzed = set(EmailAnalysisModel.objects.filter(user=user).values_list("email_id", flat=True))
        for email in EmailModel.objects.filter(user=user, mail_account_id=account.pk):
            if email.pk in analyzed:
                continue
            key = email.external_message_id.removeprefix("fake-")
            a = EmailAnalysis.request(email_id=email.pk, user_id=UserId(user.pk),
                                      model=active_model(), prompt_version=active_prompt_version())
            if not (email.body_text.strip() or email.subject.strip()):
                a.skip("Not eligible for analysis: empty subject and body")
            elif key in PENDING_KEYS:
                pass
            elif key in FAILED_KEYS:
                a.start()
                a.fail(FAILED_KEYS[key])
            else:
                raw = fake_rules.classify(email.subject, email.body_text, email.sender_email)
                a.start()
                a.complete(AnalysisResult(
                    priority=Priority(raw["priority"]),
                    priority_confidence=Percentage(raw["priority_confidence"]),
                    spam_likelihood=Percentage(raw["spam_likelihood"]),
                    reply_urgency=Percentage(raw["reply_urgency"]),
                    category=Category(raw["category"]),
                    sentiment=Sentiment(raw["sentiment"])))
            a.pull_events()
            repo.save(a)

    def _sync_history(self, account: GmailAccountModel, imported: int) -> None:
        if EmailSyncModel.objects.filter(gmail_account=account).exists():
            return
        now = timezone.now()
        rows = [
            ("INITIAL", "COMPLETED", imported, imported, 0, "", now - timedelta(days=2)),
            ("INCREMENTAL", "FAILED", 0, 0, 0,
             "Gmail API rate limit exceeded (HTTP 429); retried with backoff",
             now - timedelta(days=1, hours=3)),
            ("INCREMENTAL", "PARTIAL", 3, 2, 1, "1 message could not be imported",
             now - timedelta(days=1)),
            ("INCREMENTAL", "COMPLETED", 0, 0, 0, "", now - timedelta(minutes=30)),
        ]
        for type_, status, fetched, imp, failed, error, started in rows:
            s = EmailSyncModel.objects.create(
                gmail_account=account, type=type_, status=status, fetched_count=fetched,
                imported_count=imp, failed_count=failed, error=error, started_at=started,
                completed_at=started + timedelta(seconds=12))
            EmailSyncModel.objects.filter(pk=s.pk).update(created_at=started)
        GmailAccountModel.objects.filter(pk=account.pk).update(last_synced_at=now - timedelta(minutes=30))
