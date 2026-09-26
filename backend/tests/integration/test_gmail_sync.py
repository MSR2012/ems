import pytest
from django.utils import timezone

from gmail_integration.domain.email_sync import SyncStatus, SyncType
from gmail_integration.domain.gmail_account import GmailAccountStatus
from gmail_integration.infrastructure import container
from gmail_integration.infrastructure.persistence.models import EmailSyncModel, GmailAccountModel
from gmail_integration.infrastructure.tasks import backoff_seconds, sync_gmail_account
from mailbox_context.infrastructure.persistence.models import EmailModel
from tests.factories import connect_fake_account, deliver_new_mail, mailbox

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture(autouse=True)
def _clear_locks():
    import redis
    from django.conf import settings

    r = redis.Redis.from_url(settings.REDIS_URL)
    for k in r.scan_iter("lock:gmail-sync:*"):
        r.delete(k)


def run_sync(account_id):
    sync = container.request_sync()(account_id=account_id, enqueue=False)
    return container.sync_account()(account_id=account_id, sync_id=sync.id)


def test_initial_sync_imports_bounded_window_and_records_history(user):
    account = connect_fake_account(user)
    sync = run_sync(account.id)
    assert sync.type == SyncType.INITIAL and sync.status == SyncStatus.COMPLETED
    n = EmailModel.objects.filter(user=user).count()
    # the dataset has one message older than 30 days (m039) which is outside the window
    assert n == 39 and sync.imported_count == 39
    acc = GmailAccountModel.objects.get(pk=account.id)
    assert acc.history_id and acc.last_synced_at and acc.next_sync_at > timezone.now()


def test_sync_twice_creates_no_duplicates(user):
    account = connect_fake_account(user)
    run_sync(account.id)
    before = EmailModel.objects.count()
    GmailAccountModel.objects.filter(pk=account.id).update(history_id="")  # force full re-sync
    second = run_sync(account.id)
    assert EmailModel.objects.count() == before
    assert second.status == SyncStatus.COMPLETED and second.imported_count == 0
    assert second.fetched_count == before


def test_incremental_sync_imports_only_new_messages(user):
    account = connect_fake_account(user)
    run_sync(account.id)
    before = EmailModel.objects.count()
    deliver_new_mail(account)
    sync = run_sync(account.id)
    assert sync.type == SyncType.INCREMENTAL
    assert sync.fetched_count == 3 and sync.imported_count == 3
    assert EmailModel.objects.count() == before + 3


def test_expired_history_falls_back_to_bounded_full_resync(user):
    account = connect_fake_account(user)
    run_sync(account.id)
    GmailAccountModel.objects.filter(pk=account.id).update(history_id="5")  # too old for fake
    sync = run_sync(account.id)
    assert sync.status == SyncStatus.COMPLETED and sync.type == SyncType.INCREMENTAL
    assert sync.fetched_count == 39 and sync.imported_count == 0


def test_revoked_authorization_marks_account_and_stops_schedule(user):
    account = connect_fake_account(user)
    box = mailbox(account)
    box.revoked = True
    box.save()
    sync = run_sync(account.id)
    assert sync.status == SyncStatus.FAILED and "reconnect" in sync.error.lower()
    acc = container.accounts().get(account.id)
    assert acc.status == GmailAccountStatus.REVOKED and acc.next_sync_at is None
    assert container.dispatch_due_syncs()() == 0
    from gmail_integration.application.use_cases import SyncNotAllowed

    with pytest.raises(SyncNotAllowed):
        container.request_sync()(account_id=account.id)


def test_expired_token_is_refreshed_server_side(user):
    from datetime import timedelta

    account = connect_fake_account(user, expires_in=timedelta(seconds=-10))
    old_cipher = GmailAccountModel.objects.get(pk=account.id).encrypted_access_token
    sync = run_sync(account.id)
    assert sync.status == SyncStatus.COMPLETED
    acc = GmailAccountModel.objects.get(pk=account.id)
    assert acc.encrypted_access_token != old_cipher and acc.token_expires_at > timezone.now()


def test_rate_limit_is_retried_with_backoff_and_visible_in_history(user, settings):
    account = connect_fake_account(user)
    box = mailbox(account)
    box.rate_limit_failures = 1
    box.save()
    sync = container.request_sync()(account_id=account.id, enqueue=False)
    sync_gmail_account.apply(kwargs={"account_id": account.id, "sync_id": sync.id}, throw=False)
    rows = list(EmailSyncModel.objects.filter(gmail_account_id=account.id).order_by("id"))
    assert rows[0].status == "FAILED" and "rate limit" in rows[0].error.lower()
    assert rows[-1].status == "COMPLETED"  # the retry (eager) succeeded
    assert EmailModel.objects.filter(user=user).count() == 39


def test_backoff_grows_exponentially_with_jitter():
    assert 5 <= backoff_seconds(0) <= 6
    assert 20 <= backoff_seconds(2) <= 25
    assert backoff_seconds(10) <= 300 + 75
    assert backoff_seconds(0, retry_after=30) >= 30


def test_dispatch_due_syncs_enqueues_only_due_active_accounts(user, make_user):
    a = connect_fake_account(user)
    other = make_user(email="bob@example.com")
    b = connect_fake_account(other)
    GmailAccountModel.objects.filter(pk=b.id).update(next_sync_at=timezone.now() + timezone.timedelta(hours=1))
    assert container.dispatch_due_syncs()() == 1  # eager: runs the sync for `a`
    assert EmailSyncModel.objects.filter(gmail_account_id=a.id, status="COMPLETED").exists()
    assert not EmailSyncModel.objects.filter(gmail_account_id=b.id).exists()


def test_concurrent_sync_is_prevented_by_lock(user):
    from gmail_integration.application.use_cases import RetryableSyncError
    from gmail_integration.infrastructure.adapters import RedisAccountLock

    account = connect_fake_account(user)
    sync = container.request_sync()(account_id=account.id, enqueue=False)
    lock = RedisAccountLock()
    assert lock.acquire(account.id)
    try:
        with pytest.raises(RetryableSyncError):
            container.sync_account()(account_id=account.id, sync_id=sync.id)
    finally:
        lock.release(account.id)


def test_second_request_while_pending_is_rejected(user):
    from gmail_integration.application.use_cases import SyncAlreadyRunning

    account = connect_fake_account(user)
    container.request_sync()(account_id=account.id, enqueue=False)
    with pytest.raises(SyncAlreadyRunning):
        container.request_sync()(account_id=account.id, enqueue=False)
