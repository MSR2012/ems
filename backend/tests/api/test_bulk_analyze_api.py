"""POST /emails/analyze — the "Analyze with Jev AI" button: queues the user's inbox for analysis."""

import pytest
from django.core.management import call_command
from rest_framework.test import APIClient

from email_intelligence.infrastructure.ai.fake import set_failure_mode
from email_intelligence.infrastructure.persistence.models import EmailAnalysisModel
from identity.infrastructure.persistence.models import UserModel
from mailbox_context.infrastructure.persistence.models import EmailModel

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def demo(db):
    set_failure_mode("none")
    call_command("seed_demo", verbosity=0)
    user = UserModel.objects.get(email="demo@example.com")
    c = APIClient()
    c.force_login(user)
    return user, c


def test_button_endpoint_queues_missing_and_failed_analyses_via_task(demo):
    user, c = demo
    r = c.post("/api/v1/emails/analyze", {}, format="json")
    assert r.status_code == 202
    body = r.json()
    assert body["status"] == "queued" and body["force"] is False
    assert body["model"] == "fake-classifier-1" and body["prompt_version"] == "v1"
    # eager celery: the fan-out task ran; seeded PENDING (2) + FAILED (2) are now completed
    statuses = set(EmailAnalysisModel.objects.filter(user=user).values_list("status", flat=True))
    assert statuses <= {"COMPLETED", "SKIPPED"}
    assert EmailAnalysisModel.objects.filter(user=user).count() == EmailModel.objects.filter(user=user).count()


def test_non_force_is_idempotent_and_skips_completed(demo):
    user, c = demo
    c.post("/api/v1/emails/analyze", {}, format="json")
    before = dict(EmailAnalysisModel.objects.filter(user=user).values_list("id", "analyzed_at"))
    from email_intelligence.infrastructure import container

    assert container.reanalyze_emails()(user_id=user.id) == 0
    after = dict(EmailAnalysisModel.objects.filter(user=user).values_list("id", "analyzed_at"))
    assert before == after


def test_force_reruns_everything_for_that_user_only(demo):
    user, c = demo
    other = UserModel.objects.get(email="other@example.com")
    other_before = dict(EmailAnalysisModel.objects.filter(user=other).values_list("id", "analyzed_at"))
    mine_before = dict(EmailAnalysisModel.objects.filter(user=user, status="COMPLETED")
                       .values_list("id", "analyzed_at"))
    assert c.post("/api/v1/emails/analyze", {"force": True}, format="json").status_code == 202
    mine_after = dict(EmailAnalysisModel.objects.filter(user=user, id__in=mine_before)
                      .values_list("id", "analyzed_at"))
    assert all(mine_after[i] > mine_before[i] for i in mine_before)
    assert dict(EmailAnalysisModel.objects.filter(user=other).values_list("id", "analyzed_at")) == other_before


def test_switching_provider_analyzes_inbox_with_new_model(demo, settings):
    """E.g. AI_PROVIDER switched to Jev AI: the button creates new rows for the new model."""
    user, c = demo
    from unittest import mock

    settings.AI_PROVIDER = "jev_ai"
    settings.JEV_AI_MODEL = "jev-latest"
    from email_intelligence.application.ports import ClassificationOutcome
    from email_intelligence.domain.classifications import (
        AnalysisResult,
        Category,
        Percentage,
        Priority,
    )

    outcome = ClassificationOutcome(result=AnalysisResult(
        priority=Priority.NORMAL, priority_confidence=Percentage(70), spam_likelihood=Percentage(5),
        reply_urgency=Percentage(40), category=Category.WORK), input_tokens=1, output_tokens=1,
        model_version="jev-1.13.0")
    with mock.patch("email_intelligence.infrastructure.ai.jev_ai.JevAIClassifier.classify",
                    return_value=outcome):
        r = c.post("/api/v1/emails/analyze", {}, format="json")
    assert r.json()["provider"] == "jev_ai" and r.json()["model"] == "jev-latest"
    jev_rows = EmailAnalysisModel.objects.filter(user=user, model="jev-latest")
    assert jev_rows.filter(status="COMPLETED").count() == EmailModel.objects.filter(user=user).count() - 1
    assert jev_rows.first().model_version == "jev-1.13.0"
    e = jev_rows.filter(status="COMPLETED").first().email_id
    assert c.get(f"/api/v1/emails/{e}").json()["analysis"]["model"] == "jev-latest"


def test_requires_auth_and_csrf(demo):
    user, _ = demo
    assert APIClient().post("/api/v1/emails/analyze").status_code == 401
    c = APIClient(enforce_csrf_checks=True)
    c.force_login(user)
    assert c.post("/api/v1/emails/analyze", {}, format="json").status_code == 403


def test_management_command_force_flag(demo):
    user, _ = demo
    call_command("reanalyze_emails", "--user-id", str(user.id), "--force", verbosity=0)
    assert not EmailAnalysisModel.objects.filter(user=user, status__in=["PENDING", "FAILED"]).exists()
