import pytest

from gmail_integration.domain.email_sync import EmailSync, SyncStatus, SyncType
from gmail_integration.domain.events import EmailSyncCompleted, EmailSyncFailed
from shared_kernel.domain import InvalidStateTransition


def test_happy_path_pending_running_completed():
    s = EmailSync.request(1, SyncType.INITIAL)
    assert s.status == SyncStatus.PENDING
    s.start()
    s.record_fetched(3)
    s.record_imported(3)
    s.complete()
    assert s.status == SyncStatus.COMPLETED and s.completed_at is not None
    assert isinstance(s.pull_events()[0], EmailSyncCompleted)


def test_failures_make_sync_partial():
    s = EmailSync.request(1, SyncType.INCREMENTAL)
    s.start()
    s.record_imported(2)
    s.record_failure()
    s.complete()
    assert s.status == SyncStatus.PARTIAL


def test_fail_records_error_and_event():
    s = EmailSync.request(1, SyncType.INITIAL)
    s.start()
    s.fail("rate limited")
    assert s.status == SyncStatus.FAILED and s.error == "rate limited"
    assert isinstance(s.pull_events()[0], EmailSyncFailed)


@pytest.mark.parametrize("final", ["complete", "fail"])
def test_finished_sync_cannot_return_to_running(final):
    s = EmailSync.request(1, SyncType.INITIAL)
    s.start()
    getattr(s, final)(*(["x"] if final == "fail" else []))
    with pytest.raises(InvalidStateTransition):
        s.start()


def test_cannot_complete_pending_or_count_when_not_running():
    s = EmailSync.request(1, SyncType.INITIAL)
    with pytest.raises(InvalidStateTransition):
        s.complete()
    with pytest.raises(InvalidStateTransition):
        s.record_imported()
    s.fail("never started")  # PENDING → FAILED is allowed
    assert s.status == SyncStatus.FAILED
