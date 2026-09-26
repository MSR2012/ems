"""Security suite (§28.5): cross-user access, stored XSS, CSRF, authorization bypass,
token exposure (API, DB, logs)."""

import io
import json
import logging
import re

import pytest
from django.core.management import call_command
from rest_framework.test import APIClient

from email_intelligence.infrastructure.persistence.models import EmailAnalysisModel
from gmail_integration.infrastructure.persistence.models import EmailSyncModel, GmailAccountModel
from identity.infrastructure.persistence.models import UserModel
from mailbox_context.infrastructure.persistence.models import EmailModel
from shared_kernel.infrastructure.logging import SensitiveDataFilter, redact

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def world(db):
    import redis
    from django.conf import settings

    r = redis.Redis.from_url(settings.REDIS_URL)
    for k in r.scan_iter("lock:gmail-sync:*"):
        r.delete(k)
    call_command("seed_demo", verbosity=0)
    demo = UserModel.objects.get(email="demo@example.com")
    other = UserModel.objects.get(email="other@example.com")
    return demo, other


def client(user=None, csrf=False):
    c = APIClient(enforce_csrf_checks=csrf)
    if user:
        c.force_login(user)
    return c


# --- cross-user access / IDOR -------------------------------------------------------------
def test_cross_user_access_is_404_everywhere(world):
    demo, other = world
    e = EmailModel.objects.filter(user=demo).first()
    acc = GmailAccountModel.objects.get(user=demo)
    attacker = client(other)
    probes = [
        ("get", f"/api/v1/emails/{e.id}"),
        ("get", f"/api/v1/threads/{e.external_thread_id}-nonexistent"),
        ("get", "/api/v1/threads/fake-t-mom"),
        ("post", f"/api/v1/emails/{e.id}/reanalyze"),
        ("delete", f"/api/v1/integrations/gmail/{acc.id}"),
        ("post", f"/api/v1/integrations/gmail/{acc.id}/sync"),
        ("get", f"/api/v1/integrations/gmail/{acc.id}/syncs"),
        ("post", f"/api/v1/demo/gmail/{acc.id}/revoke"),
        ("post", f"/api/v1/demo/gmail/{acc.id}/new-messages"),
        ("post", f"/api/v1/demo/gmail/{acc.id}/rate-limit"),
    ]
    for method, path in probes:
        assert getattr(attacker, method)(path).status_code == 404, path
    assert GmailAccountModel.objects.get(pk=acc.id).status == "ACTIVE"


def test_lists_and_dashboards_never_leak_other_users_data(world):
    demo, other = world
    demo_ids = set(EmailModel.objects.filter(user=demo).values_list("id", flat=True))
    c = client(other)
    seen = {r["id"] for r in c.get("/api/v1/emails", {"page_size": 100}).json()["results"]}
    seen |= {r["email"]["id"] for r in c.get("/api/v1/dashboard/needs-attention", {"limit": 50}).json()["results"]}
    seen |= {r["id"] for r in c.get("/api/v1/dashboard/summary").json()["recent"]}
    assert seen and not seen & demo_ids
    assert c.get("/api/v1/dashboard/summary").json()["counts"]["total"] == EmailModel.objects.filter(user=other).count()
    assert c.get("/api/v1/integrations/gmail").json()["account"]["email"] == "other.inbox@gmail.com"


def test_client_supplied_user_fields_are_ignored(world):
    demo, other = world
    c = client(other)
    r = c.get("/api/v1/emails", {"user_id": demo.id, "user": demo.id, "page_size": 100})
    assert {x["id"] for x in r.json()["results"]} == set(EmailModel.objects.filter(user=other).values_list("id", flat=True))
    r = c.patch("/api/v1/me", {"id": demo.id, "email": "demo@example.com", "name": "Hacker"}, format="json")
    assert r.status_code == 200 and r.json()["email"] == "other@example.com"
    demo.refresh_from_db()
    assert demo.name == "Demo User"


def test_unauthenticated_access_is_rejected(world):
    anon = client()
    for method, path in [("get", "/api/v1/emails"), ("get", "/api/v1/emails/1"), ("get", "/api/v1/threads/x"),
                         ("get", "/api/v1/dashboard/summary"), ("get", "/api/v1/dashboard/needs-attention"),
                         ("get", "/api/v1/integrations/gmail"), ("post", "/api/v1/emails/1/reanalyze"),
                         ("get", "/api/v1/me"), ("post", "/api/v1/demo/ai/failure-mode"),
                         ("get", "/api/v1/ops/metrics")]:
        assert getattr(anon, method)(path).status_code in (401, 403), path


def test_ops_metrics_is_staff_only(world):
    demo, _ = world
    assert client(demo).get("/api/v1/ops/metrics").status_code == 403
    demo.is_staff = True
    demo.save()
    body = client(demo).get("/api/v1/ops/metrics").json()["metrics"]
    assert body["emails_total"] >= 45 and "COMPLETED" in body["analyses_by_status"]


# --- CSRF --------------------------------------------------------------------------------
def test_unsafe_methods_without_csrf_are_rejected(world):
    demo, _ = world
    e = EmailModel.objects.filter(user=demo).first()
    acc = GmailAccountModel.objects.get(user=demo)
    c = client(demo, csrf=True)
    for method, path in [("post", f"/api/v1/emails/{e.id}/reanalyze"),
                         ("post", f"/api/v1/integrations/gmail/{acc.id}/sync"),
                         ("delete", f"/api/v1/integrations/gmail/{acc.id}"),
                         ("patch", "/api/v1/me"), ("post", "/api/v1/auth/logout"),
                         ("post", "/api/v1/me/password"), ("post", "/api/v1/demo/ai/failure-mode")]:
        assert getattr(c, method)(path, {}, format="json").status_code == 403, path
    assert GmailAccountModel.objects.get(pk=acc.id).status == "ACTIVE"


def test_oauth_callback_requires_matching_state(world):
    demo, _ = world
    c = client(demo)
    r = c.get("/api/v1/integrations/gmail/callback", {"code": "anything", "state": "forged"})
    assert "state_mismatch" in r["Location"]


def test_session_cookie_flags():
    from django.conf import settings

    assert settings.SESSION_COOKIE_HTTPONLY and settings.SESSION_COOKIE_SAMESITE == "Lax"
    assert settings.CORS_ALLOWED_ORIGINS == [settings.FRONTEND_URL] or settings.CORS_ALLOWED_ORIGINS
    assert "*" not in settings.CORS_ALLOWED_ORIGINS


def test_cors_rejects_foreign_origin(world):
    r = client().get("/api/v1/health", HTTP_ORIGIN="https://evil.example.com")
    assert "access-control-allow-origin" not in {k.lower() for k in r.headers}
    r = client().get("/api/v1/health", HTTP_ORIGIN="http://localhost:5173")
    assert r.headers.get("Access-Control-Allow-Origin") == "http://localhost:5173"


# --- stored XSS --------------------------------------------------------------------------
XSS_PAYLOADS = [
    "<script>alert(1)</script>", '<img src=x onerror="alert(1)">', '<a href="javascript:alert(1)">x</a>',
    '<svg onload="alert(1)"></svg>', '<iframe src="https://evil.example.com"></iframe>',
    '<div style="background:url(https://t.example.com/p)">x</div>', '<body onload=alert(1)>',
    '<img src="https://tracker.example.com/pixel.gif">', '<math><mi xlink:href="javascript:alert(1)">x</mi></math>',
    '<form action="https://evil.example.com"><input name=p></form>', '<meta http-equiv="refresh" content="0;url=https://evil.example.com">',
    '<object data="https://evil.example.com/x.swf"></object>', '<a href="data:text/html;base64,PHNjcmlwdD4=">d</a>',
]


@pytest.mark.parametrize("payload", XSS_PAYLOADS)
def test_stored_xss_is_neutralized(world, payload):
    from mailbox_context.infrastructure.content.sanitizer import NH3ContentProcessor

    out = NH3ContentProcessor().process(html=f"<p>hi</p>{payload}", text="").sanitized_html.lower()
    for bad in ("<script", "onerror", "onload", "javascript:", "<iframe", "<svg", "url(", "evil.example.com",
                "tracker.example.com", "<form", "<meta", "<object", "data:text/html"):
        assert bad not in out, (payload, out)


def test_seeded_xss_email_is_safe_in_api(world):
    demo, _ = world
    e = EmailModel.objects.get(user=demo, external_message_id="fake-m029")
    html = client(demo).get(f"/api/v1/emails/{e.id}").json()["body_html_sanitized"].lower()
    assert "<script" not in html and "onerror" not in html and "tracker.example.com" not in html


# --- token exposure ----------------------------------------------------------------------
TOKEN_RE = re.compile(r"fake-(at|rt)-|gAAAAA|access_token|refresh_token|encrypted_", re.I)


def test_no_api_response_contains_tokens(world):
    demo, _ = world
    acc = GmailAccountModel.objects.get(user=demo)
    c = client(demo)
    for path in ["/api/v1/integrations/gmail", f"/api/v1/integrations/gmail/{acc.id}/syncs", "/api/v1/me",
                 "/api/v1/auth/session", "/api/v1/dashboard/summary", "/api/v1/emails",
                 "/api/v1/dashboard/needs-attention"]:
        assert not TOKEN_RE.search(c.get(path).content.decode()), path


def test_tokens_are_ciphertext_at_rest(world):
    for acc in GmailAccountModel.objects.exclude(encrypted_access_token=""):
        assert acc.encrypted_access_token.startswith("gAAAAA")
        assert "fake-" not in acc.encrypted_access_token and "fake-" not in acc.encrypted_refresh_token


def test_logs_from_full_flow_contain_no_bodies_or_tokens(world, settings):
    """Run sync + analysis with the production log pipeline attached and grep the output."""
    from pythonjsonlogger import jsonlogger

    from gmail_integration.infrastructure import container as gmail
    from tests.factories import connect_fake_account, deliver_new_mail

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(jsonlogger.JsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    handler.addFilter(SensitiveDataFilter())
    root = logging.getLogger()
    old_level = root.level
    root.addHandler(handler)
    root.setLevel(logging.DEBUG)
    try:
        user = UserModel.objects.create_user(email="logs@example.com", password="Sup3r-Secret-pw")
        acc = connect_fake_account(user)
        s = gmail.request_sync()(account_id=acc.id, enqueue=False)
        gmail.sync_account()(account_id=acc.id, sync_id=s.id)
        deliver_new_mail(acc)
        s = gmail.request_sync()(account_id=acc.id, enqueue=False)
        gmail.sync_account()(account_id=acc.id, sync_id=s.id)
        logging.getLogger("probe").warning("token leak attempt access_token=abc123 Bearer xyz.987",
                                           extra={"body_text": "Dad is making lasagna", "refresh_token": "r1"})
    finally:
        root.removeHandler(handler)
        root.setLevel(old_level)
    out = stream.getvalue()
    assert out  # something was logged
    for secret in ("lasagna", "Production environment has been down", "fake-at-", "fake-rt-",
                   "ACCESS-SECRET", "REFRESH-SECRET", "gAAAAA", "abc123", "xyz.987"):
        assert secret not in out, secret
    assert EmailSyncModel.objects.filter(gmail_account_id=acc.id, status="COMPLETED").count() == 2
    assert EmailAnalysisModel.objects.filter(user=user, status="COMPLETED").exists()
    for line in out.strip().splitlines():
        json.loads(line)  # structured JSON


def test_redact_helper():
    assert redact("Authorization: Bearer ya29.abc-DEF") == "Authorization: Bearer [REDACTED]"
    assert "[REDACTED]" in redact("refresh_token=1//0abcdefghijklmnopqrstuvwxyz")
    assert redact("/callback?code=4/abc&state=x").startswith("/callback?code=[REDACTED]")
    assert redact('"GET /api/v1/emails?q=lasagna&page=2 HTTP/1.1"') == '"GET /api/v1/emails?q=[REDACTED]&page=2 HTTP/1.1"'
