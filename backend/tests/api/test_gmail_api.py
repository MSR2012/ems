import re
from urllib.parse import parse_qs, urlparse

import pytest
from rest_framework.test import APIClient

from gmail_integration.infrastructure.persistence.models import EmailSyncModel, GmailAccountModel
from mailbox_context.infrastructure.persistence.models import EmailModel
from tests.factories import connect_fake_account

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture(autouse=True)
def _clear_locks():
    import redis
    from django.conf import settings

    r = redis.Redis.from_url(settings.REDIS_URL)
    for k in r.scan_iter("lock:gmail-sync:*"):
        r.delete(k)


def oauth_connect(client):
    r = client.get("/api/v1/integrations/gmail/connect")
    assert r.status_code == 302
    consent_url = r["Location"]
    state = parse_qs(urlparse(consent_url).query)["state"][0]
    page = client.get(urlparse(consent_url).path, {"state": state})
    assert page.status_code == 200
    html = page.content.decode()
    assert 'type="password"' not in html  # never asks for a Gmail password
    allow = re.search(r'id="allow" href="([^"]+)"', html).group(1).replace("&amp;", "&")
    return state, allow


def test_connect_flow_with_state_creates_encrypted_account_and_initial_sync(auth_client, user):
    state, allow = oauth_connect(auth_client)
    r = auth_client.get(urlparse(allow).path + "?" + urlparse(allow).query)
    assert r.status_code == 302 and r["Location"].endswith("/integrations?gmail=connected")
    acc = GmailAccountModel.objects.get(user=user)
    assert acc.status == "ACTIVE"
    # ciphertext only
    assert acc.encrypted_access_token.startswith("gAAAA") and "fake-at" not in acc.encrypted_access_token
    assert acc.encrypted_refresh_token.startswith("gAAAA")
    # initial sync ran (eager celery) after commit
    sync = EmailSyncModel.objects.get(gmail_account=acc)
    assert sync.type == "INITIAL" and sync.status == "COMPLETED"
    assert EmailModel.objects.filter(user=user).count() > 0
    body = auth_client.get("/api/v1/integrations/gmail").json()
    assert body["connected"] and body["account"]["status"] == "ACTIVE"
    assert "token" not in str(body).lower()


def test_callback_rejects_state_mismatch(auth_client, user):
    oauth_connect(auth_client)
    r = auth_client.get("/api/v1/integrations/gmail/callback", {"code": "x", "state": "forged"})
    assert "gmail=error" in r["Location"] and "state_mismatch" in r["Location"]
    assert not GmailAccountModel.objects.filter(user=user).exists()


def test_callback_without_prior_connect_is_rejected(auth_client, user):
    r = auth_client.get("/api/v1/integrations/gmail/callback", {"code": "x", "state": "abc"})
    assert "state_mismatch" in r["Location"]


def test_callback_denied(auth_client, user):
    state, _ = oauth_connect(auth_client)
    r = auth_client.get("/api/v1/integrations/gmail/callback", {"error": "access_denied", "state": state})
    assert r["Location"].endswith("/integrations?gmail=denied")
    assert not GmailAccountModel.objects.filter(user=user).exists()


def test_callback_with_invalid_code(auth_client, user):
    state, _ = oauth_connect(auth_client)
    r = auth_client.get("/api/v1/integrations/gmail/callback", {"code": "tampered", "state": state})
    assert "exchange_failed" in r["Location"]


def test_connect_requires_login():
    r = APIClient().get("/api/v1/integrations/gmail/connect")
    assert r.status_code == 302 and "/login" in r["Location"]


def test_disconnect_deletes_credentials(auth_client, user):
    account = connect_fake_account(user)
    r = auth_client.delete(f"/api/v1/integrations/gmail/{account.id}")
    assert r.status_code == 204
    acc = GmailAccountModel.objects.get(pk=account.id)
    assert acc.status == "DISCONNECTED" and acc.encrypted_access_token == "" and acc.encrypted_refresh_token == ""
    body = auth_client.get("/api/v1/integrations/gmail").json()
    assert body["connected"] is False and body["account"] is None


def test_reconnect_after_revoke_restores_syncing(auth_client, user):
    state, allow = oauth_connect(auth_client)
    auth_client.get(urlparse(allow).path + "?" + urlparse(allow).query)
    acc = GmailAccountModel.objects.get(user=user)
    auth_client.post(f"/api/v1/demo/gmail/{acc.id}/revoke")
    r = auth_client.post(f"/api/v1/integrations/gmail/{acc.id}/sync")
    assert r.status_code == 202
    acc.refresh_from_db()
    assert acc.status == "REVOKED"
    assert auth_client.post(f"/api/v1/integrations/gmail/{acc.id}/sync").status_code == 400
    state, allow = oauth_connect(auth_client)
    auth_client.get(urlparse(allow).path + "?" + urlparse(allow).query)
    acc.refresh_from_db()
    assert acc.status == "ACTIVE" and GmailAccountModel.objects.filter(user=user).count() == 1
    assert EmailSyncModel.objects.filter(gmail_account=acc).order_by("-id").first().status == "COMPLETED"


def test_manual_sync_and_history(auth_client, user):
    account = connect_fake_account(user)
    r = auth_client.post(f"/api/v1/integrations/gmail/{account.id}/sync")
    assert r.status_code == 202 and r.json()["status"] == "PENDING"
    syncs = auth_client.get(f"/api/v1/integrations/gmail/{account.id}/syncs").json()
    assert syncs["count"] == 1 and syncs["results"][0]["status"] == "COMPLETED"


def test_other_users_account_is_404(auth_client, make_user):
    other = make_user(email="mallory@example.com")
    account = connect_fake_account(other)
    for method, path in [("delete", f"/api/v1/integrations/gmail/{account.id}"),
                         ("post", f"/api/v1/integrations/gmail/{account.id}/sync"),
                         ("get", f"/api/v1/integrations/gmail/{account.id}/syncs"),
                         ("post", f"/api/v1/demo/gmail/{account.id}/revoke")]:
        assert getattr(auth_client, method)(path).status_code == 404, path
    assert GmailAccountModel.objects.get(pk=account.id).status == "ACTIVE"


def test_demo_new_messages_then_incremental_sync(auth_client, user):
    account = connect_fake_account(user)
    auth_client.post(f"/api/v1/integrations/gmail/{account.id}/sync")
    before = EmailModel.objects.filter(user=user).count()
    assert auth_client.post(f"/api/v1/demo/gmail/{account.id}/new-messages").status_code == 200
    auth_client.post(f"/api/v1/integrations/gmail/{account.id}/sync")
    latest = EmailSyncModel.objects.filter(gmail_account_id=account.id).first()
    assert latest.type == "INCREMENTAL" and latest.imported_count == 3
    assert EmailModel.objects.filter(user=user).count() == before + 3


def test_gmail_endpoints_require_auth():
    c = APIClient()
    assert c.get("/api/v1/integrations/gmail").status_code == 401
    assert c.post("/api/v1/integrations/gmail/1/sync").status_code == 401
