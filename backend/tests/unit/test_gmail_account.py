from datetime import UTC, datetime, timedelta

import pytest

from gmail_integration.domain.events import (
    GmailAccountConnected,
    GmailAccountDisconnected,
    GmailAuthorizationRevoked,
)
from gmail_integration.domain.gmail_account import GmailAccount, GmailAccountStatus
from gmail_integration.domain.value_objects import HistoryId, OAuthCredentials
from shared_kernel.domain import InvalidStateTransition, InvariantViolation, UserId

NOW = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)


def creds(**kw):
    return OAuthCredentials(access_token=kw.get("a", "access"), refresh_token="refresh",
                            expires_at=kw.get("exp", NOW + timedelta(hours=1)),
                            scopes=("gmail.readonly",))


def account():
    a = GmailAccount.connect(user_id=UserId(1), google_account_id="g-1", email="u@gmail.com",
                             credentials=creds(), now=NOW)
    a.id = 10
    return a


def test_connect_is_active_and_due_immediately():
    a = account()
    assert a.status == GmailAccountStatus.ACTIVE
    assert a.is_due(NOW)
    a.mark_connected()
    assert isinstance(a.pull_events()[0], GmailAccountConnected)


def test_credentials_repr_hides_tokens():
    assert "access" not in repr(creds(a="secret-token-xyz"))
    assert "secret-token-xyz" not in repr(account())


def test_credentials_expiry():
    assert creds(exp=NOW + timedelta(seconds=30)).is_expired(NOW)
    assert not creds(exp=NOW + timedelta(hours=1)).is_expired(NOW)
    with pytest.raises(InvariantViolation):
        OAuthCredentials(access_token="", refresh_token="r")


def test_revoke_stops_scheduled_syncs_and_raises_event():
    a = account()
    a.revoke()
    assert a.status == GmailAccountStatus.REVOKED
    assert not a.can_sync and not a.is_due(NOW + timedelta(days=1))
    assert isinstance(a.pull_events()[0], GmailAuthorizationRevoked)
    a.revoke()  # idempotent
    assert a.pull_events() == []


def test_reconnect_restores_syncing():
    a = account()
    a.revoke()
    a.pull_events()
    a.reconnect(email="u@gmail.com", credentials=creds(a="new"), now=NOW)
    assert a.status == GmailAccountStatus.ACTIVE and a.is_due(NOW)
    ev = a.pull_events()[0]
    assert isinstance(ev, GmailAccountConnected) and ev.reconnected


def test_disconnect_deletes_credentials():
    a = account()
    a.disconnect()
    assert a.credentials is None and a.status == GmailAccountStatus.DISCONNECTED
    assert isinstance(a.pull_events()[0], GmailAccountDisconnected)
    with pytest.raises(InvalidStateTransition):
        a.revoke()


def test_record_sync_success_moves_history_forward_only():
    a = account()
    a.record_sync_success(history_id=HistoryId("200"), now=NOW, interval=timedelta(minutes=5))
    a.record_sync_success(history_id=HistoryId("100"), now=NOW, interval=timedelta(minutes=5))
    assert str(a.history_id) == "200"
    assert a.next_sync_at == NOW + timedelta(minutes=5)
    assert not a.is_due(NOW)


def test_history_id_must_be_numeric():
    with pytest.raises(InvariantViolation):
        HistoryId("abc")


def test_error_status_recovers_after_success():
    a = account()
    a.mark_error("boom")
    assert a.status == GmailAccountStatus.ERROR and a.can_sync
    a.record_sync_success(history_id=None, now=NOW, interval=timedelta(minutes=5))
    assert a.status == GmailAccountStatus.ACTIVE
