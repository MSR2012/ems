from datetime import timedelta

import pytest
from django.core.management import call_command
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from email_intelligence.infrastructure.persistence.models import EmailAnalysisModel
from identity.infrastructure.persistence.models import UserModel
from mailbox_context.infrastructure.persistence.models import EmailModel

pytestmark = pytest.mark.django_db


@pytest.fixture
def seeded(db):
    call_command("seed_demo", verbosity=0)
    demo = UserModel.objects.get(email="demo@example.com")
    other = UserModel.objects.get(email="other@example.com")
    return demo, other


@pytest.fixture
def client_for():
    def _c(user):
        c = APIClient()
        c.force_login(user)
        return c
    return _c


def emails(client, **params):
    r = client.get("/api/v1/emails", params)
    assert r.status_code == 200, r.content
    return r.json()


def test_inbox_newest_first_paginated(seeded, client_for):
    demo, _ = seeded
    c = client_for(demo)
    total = EmailModel.objects.filter(user=demo).count()
    p1 = emails(c, page_size=10)
    assert p1["count"] == total and len(p1["results"]) == 10 and p1["next"] == 2
    dates = [r["received_at"] for r in p1["results"]]
    assert dates == sorted(dates, reverse=True)
    p2 = emails(c, page_size=10, page=2)
    assert {r["id"] for r in p1["results"]}.isdisjoint({r["id"] for r in p2["results"]})
    assert p2["previous"] == 1
    assert p2["results"][0]["received_at"] <= p1["results"][-1]["received_at"]


def test_page_size_is_capped(seeded, client_for):
    demo, _ = seeded
    r = client_for(demo).get("/api/v1/emails", {"page_size": 1000})
    assert r.status_code == 400  # never returns the full mailbox in one request


def test_other_users_emails_never_listed(seeded, client_for):
    demo, other = seeded
    ids = {r["id"] for r in emails(client_for(other), page_size=100)["results"]}
    assert ids == set(EmailModel.objects.filter(user=other).values_list("id", flat=True))
    assert not ids & set(EmailModel.objects.filter(user=demo).values_list("id", flat=True))


@pytest.mark.parametrize("q,expect", [
    ("priya", "Priya Shah"),                 # sender name
    ("acme-corp.com", "priya.shah@acme-corp.com"),  # sender email / domain
    ("lasagna", "Mom"),                      # body text
    ("invoic", "Billing — CloudHost"),       # prefix match while typing
])
def test_search(seeded, client_for, q, expect):
    demo, _ = seeded
    res = emails(client_for(demo), q=q)["results"]
    assert res and all(expect in (r["sender_name"], r["sender_email"]) for r in res), [r["subject"] for r in res]


def test_search_subject(seeded, client_for):
    demo, _ = seeded
    res = emails(client_for(demo), q="board deck")["results"]
    assert len(res) == 3 and all("board deck" in r["subject"].lower() for r in res)


def test_search_with_tsquery_syntax_is_safe(seeded, client_for):
    demo, _ = seeded
    assert emails(client_for(demo), q="':* & | ! ( )")["count"] == 0


def _analysis(eid):
    return EmailAnalysisModel.objects.filter(email_id=eid, status="COMPLETED").order_by("-analyzed_at").first()


def test_priority_and_category_filters(seeded, client_for):
    demo, _ = seeded
    c = client_for(demo)
    res = emails(c, priority="CRITICAL,HIGH", page_size=100)["results"]
    assert res and all(r["analysis"]["priority"] in ("CRITICAL", "HIGH") for r in res)
    expected = EmailAnalysisModel.objects.filter(user=demo, status="COMPLETED",
                                                 priority__in=["CRITICAL", "HIGH"]).count()
    assert len(res) == expected
    res = emails(c, category="NEWSLETTER", page_size=100)["results"]
    assert res and all(r["analysis"]["category"] == "NEWSLETTER" for r in res)


def test_percentage_range_filters(seeded, client_for):
    demo, _ = seeded
    c = client_for(demo)
    res = emails(c, spam_likelihood_min=70, page_size=100)["results"]
    assert res and all(r["analysis"]["spam_likelihood"] >= 70 and r["analysis"]["is_potential_spam"] for r in res)
    res = emails(c, reply_urgency_min=40, reply_urgency_max=90, page_size=100)["results"]
    assert res and all(40 <= r["analysis"]["reply_urgency"] <= 90 for r in res)
    r = c.get("/api/v1/emails", {"reply_urgency_min": 90, "reply_urgency_max": 10})
    assert r.status_code == 400 and "reply_urgency_max" in r.json()


def test_hide_potential_spam_keeps_unanalyzed(seeded, client_for):
    demo, _ = seeded
    c = client_for(demo)
    all_count = emails(c)["count"]
    spam = emails(c, spam_likelihood_min=70)["count"]
    res = emails(c, hide_potential_spam="true", page_size=100)
    assert res["count"] == all_count - spam
    assert any(r["analysis"] is None or r["analysis"]["status"] != "COMPLETED" for r in res["results"])


def test_read_state_and_date_filters(seeded, client_for):
    demo, _ = seeded
    c = client_for(demo)
    unread = emails(c, is_read="false", page_size=100)["results"]
    assert unread and all(not r["is_read"] for r in unread)
    assert len(unread) == EmailModel.objects.filter(user=demo, is_read=False).count()
    today = timezone.localdate()
    frm = (today - timedelta(days=2)).isoformat()
    res = emails(c, received_from=frm, received_to=today.isoformat(), page_size=100)["results"]
    assert res and all(r["received_at"][:10] >= frm for r in res)
    assert c.get("/api/v1/emails", {"received_from": "not-a-date"}).status_code == 400


def test_pending_and_failed_emails_are_listed_and_openable(seeded, client_for):
    demo, _ = seeded
    c = client_for(demo)
    rows = emails(c, page_size=100)["results"]
    statuses = {r["analysis"]["status"] for r in rows if r["analysis"]}
    assert {"PENDING", "FAILED", "SKIPPED", "COMPLETED"} <= statuses
    for r in rows:
        if r["analysis"] and r["analysis"]["status"] in ("PENDING", "FAILED"):
            assert c.get(f"/api/v1/emails/{r['id']}").status_code == 200


def test_detail_has_metadata_body_thread_and_attachments(seeded, client_for):
    demo, _ = seeded
    c = client_for(demo)
    e = EmailModel.objects.get(user=demo, external_message_id="fake-m002")
    d = c.get(f"/api/v1/emails/{e.id}").json()
    assert d["sender_email"] == "priya.shah@acme-corp.com" and d["recipients"]
    assert d["attachments"][0]["filename"] == "error-logs-2026-09.txt"
    assert [m["id"] for m in d["thread"]] and len(d["thread"]) == 2
    assert d["analysis"]["priority"] and d["analysis"]["model"] and d["analysis"]["prompt_version"]
    t = c.get(f"/api/v1/threads/{d['thread_id']}").json()
    assert len(t["messages"]) == 2 and t["messages"][0]["received_at"] <= t["messages"][1]["received_at"]


def test_xss_email_is_sanitized_at_rest_and_in_api(seeded, client_for):
    demo, _ = seeded
    e = EmailModel.objects.get(user=demo, external_message_id="fake-m029")
    html = client_for(demo).get(f"/api/v1/emails/{e.id}").json()["body_html_sanitized"]
    for bad in ("<script", "onerror", "onclick", "javascript:", "tracker.example.com", "<iframe", "<form", "url("):
        assert bad not in html.lower(), bad


def test_other_users_email_and_thread_are_404(seeded, client_for):
    demo, other = seeded
    e = EmailModel.objects.filter(user=demo).first()
    c = client_for(other)
    assert c.get(f"/api/v1/emails/{e.id}").status_code == 404
    only_demo_thread = "fake-t-mom"
    assert c.get(f"/api/v1/threads/{only_demo_thread}").status_code == 404
    assert c.get("/api/v1/emails/999999").status_code == 404


def test_inbox_requires_auth():
    c = APIClient()
    assert c.get("/api/v1/emails").status_code == 401
    assert c.get("/api/v1/emails/1").status_code == 401


def _count_queries(client, **params):
    with CaptureQueriesContext(connection) as ctx:
        assert client.get("/api/v1/emails", params).status_code == 200
    return len(ctx.captured_queries)


def test_inbox_query_count_is_constant(seeded, client_for):
    demo, _ = seeded
    c = client_for(demo)
    small = _count_queries(c, page_size=2)
    large = _count_queries(c, page_size=40)
    filtered = _count_queries(c, page_size=40, q="acme", priority="CRITICAL", hide_potential_spam="true")
    assert small == large == filtered, (small, large, filtered)
