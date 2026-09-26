import pytest
from django.core.management import call_command
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from email_intelligence.domain.classifications import Priority
from identity.infrastructure.persistence.models import UserModel
from mailbox_context.infrastructure.persistence.models import EmailModel

pytestmark = pytest.mark.django_db


@pytest.fixture
def demo(db):
    call_command("seed_demo", verbosity=0)
    user = UserModel.objects.get(email="demo@example.com")
    c = APIClient()
    c.force_login(user)
    return user, c


def sql_counts(user_id, spam_t, urg_t):
    with connection.cursor() as cur:
        cur.execute("""
            SELECT count(*),
                   count(*) FILTER (WHERE NOT e.is_read),
                   count(*) FILTER (WHERE a.status='COMPLETED' AND a.priority IN ('CRITICAL','HIGH')),
                   count(*) FILTER (WHERE a.status='COMPLETED' AND a.reply_urgency >= %s),
                   count(*) FILTER (WHERE a.status='COMPLETED' AND a.spam_likelihood >= %s)
            FROM emails e LEFT JOIN current_email_analyses a ON a.email_id = e.id
            WHERE e.user_id = %s""", [urg_t, spam_t, user_id])
        return dict(zip(["total", "unread", "high_priority", "high_urgency", "potential_spam"],
                        cur.fetchone(), strict=True))


def test_summary_counts_match_database(demo):
    user, c = demo
    d = c.get("/api/v1/dashboard/summary").json()
    assert d["counts"] == sql_counts(user.id, 70, 70)
    assert d["counts"]["total"] == EmailModel.objects.filter(user=user).count()
    assert d["thresholds"] == {"spam": 70, "urgency": 70}
    assert d["analysis"]["failed"] == 2 and d["analysis"]["in_progress"] == 2 and d["analysis"]["skipped"] == 1
    assert d["sync"]["connected"] and d["sync"]["last_synced_at"]
    assert len(d["recent"]) == 5
    assert [r["received_at"] for r in d["recent"]] == sorted([r["received_at"] for r in d["recent"]], reverse=True)


def test_threshold_change_changes_counts_and_attention(demo, settings):
    user, c = demo
    before = c.get("/api/v1/dashboard/summary").json()["counts"]
    na_before = c.get("/api/v1/dashboard/needs-attention", {"limit": 50}).json()
    settings.URGENCY_THRESHOLD_PERCENT = 90
    settings.SPAM_THRESHOLD_PERCENT = 5
    after = c.get("/api/v1/dashboard/summary").json()["counts"]
    assert after == sql_counts(user.id, 5, 90)
    assert after["high_urgency"] < before["high_urgency"]
    assert after["potential_spam"] > before["potential_spam"]
    na_after = c.get("/api/v1/dashboard/needs-attention", {"limit": 50}).json()
    assert na_after["thresholds"] == {"spam": 5, "urgency": 90}
    assert na_after["total"] < na_before["total"]
    assert all(r["analysis"]["spam_likelihood"] < 5 for r in na_after["results"])


def test_needs_attention_follows_documented_ordering_and_excludes_spam(demo):
    user, c = demo
    d = c.get("/api/v1/dashboard/needs-attention", {"limit": 50}).json()
    assert d["ai_suggestion"] is True and "AI-based suggestion" in d["description"]
    rows = d["results"]
    assert rows and d["total"] == len(rows)
    for r in rows:
        a = r["analysis"]
        assert a["spam_likelihood"] < 70
        assert a["reply_urgency"] >= 70 or a["priority"] in ("CRITICAL", "HIGH")
        assert r["reasons"]
    keys = [(-r["analysis"]["reply_urgency"], -Priority(r["analysis"]["priority"]).rank,
             r["email"]["is_read"], r["email"]["received_at"][::-1]) for r in rows]
    urg_prio = [k[:3] for k in keys]
    assert urg_prio == sorted(urg_prio)
    # spam emails never appear even if urgent/critical
    spam_ids = set(EmailModel.objects.filter(user=user, current_analysis__spam_likelihood__gte=70)
                   .values_list("id", flat=True))
    assert spam_ids and not spam_ids & {r["email"]["id"] for r in rows}


def test_needs_attention_limit_and_user_scoping(demo):
    user, c = demo
    assert len(c.get("/api/v1/dashboard/needs-attention", {"limit": 2}).json()["results"]) == 2
    other = APIClient()
    other.force_login(UserModel.objects.get(email="other@example.com"))
    ids = {r["email"]["id"] for r in other.get("/api/v1/dashboard/needs-attention").json()["results"]}
    assert ids <= set(EmailModel.objects.filter(user__email="other@example.com").values_list("id", flat=True))


def test_dashboard_query_counts_are_constant(demo):
    user, c = demo
    def count(path):
        with CaptureQueriesContext(connection) as ctx:
            assert c.get(path).status_code == 200
        return len(ctx.captured_queries)
    a = count("/api/v1/dashboard/needs-attention?limit=2")
    b = count("/api/v1/dashboard/needs-attention?limit=50")
    assert a == b
    s1 = count("/api/v1/dashboard/summary")
    call_command("seed_demo", verbosity=0)
    assert count("/api/v1/dashboard/summary") == s1


def test_new_analyzed_emails_are_reflected(demo, settings):
    from gmail_integration.infrastructure import container as gmail
    from gmail_integration.infrastructure.persistence.models import GmailAccountModel
    from tests.factories import deliver_new_mail

    user, c = demo
    before = c.get("/api/v1/dashboard/summary").json()["counts"]
    acc = gmail.accounts().get(GmailAccountModel.objects.get(user=user).id)
    deliver_new_mail(acc)
    s = gmail.request_sync()(account_id=acc.id, enqueue=False)
    gmail.sync_account()(account_id=acc.id, sync_id=s.id)
    after = c.get("/api/v1/dashboard/summary").json()
    assert after["counts"]["total"] == before["total"] + 3
    assert after["recent"][0]["subject"].startswith(("Customer follow-up", "Weekly digest", "Lunch"))
    assert after["counts"] == sql_counts(user.id, 70, 70)


def test_dashboard_requires_auth():
    c = APIClient()
    assert c.get("/api/v1/dashboard/summary").status_code == 401
    assert c.get("/api/v1/dashboard/needs-attention").status_code == 401
