import pytest
from django.core.management import call_command
from rest_framework.test import APIClient

from email_intelligence.infrastructure.ai.fake import set_failure_mode
from email_intelligence.infrastructure.persistence.models import AiUsageLogModel, EmailAnalysisModel
from gmail_integration.infrastructure import container as gmail
from mailbox_context.infrastructure.persistence.models import EmailModel
from tests.factories import connect_fake_account, deliver_new_mail

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture(autouse=True)
def _reset():
    import redis
    from django.conf import settings

    set_failure_mode("none")
    r = redis.Redis.from_url(settings.REDIS_URL)
    for k in r.scan_iter("lock:gmail-sync:*"):
        r.delete(k)
    yield
    set_failure_mode("none")


def sync(account):
    s = gmail.request_sync()(account_id=account.id, enqueue=False)
    return gmail.sync_account()(account_id=account.id, sync_id=s.id)


def test_imported_emails_are_analyzed_with_versions(user):
    account = connect_fake_account(user)
    sync(account)
    emails = EmailModel.objects.filter(user=user)
    rows = EmailAnalysisModel.objects.filter(user=user)
    assert rows.count() == emails.count()
    completed = rows.filter(status="COMPLETED")
    assert completed.count() == emails.count() - 1  # the empty scanner email is SKIPPED
    assert rows.filter(status="SKIPPED").count() == 1
    for a in completed:
        assert a.priority and a.category and 0 <= a.spam_likelihood <= 100 and 0 <= a.reply_urgency <= 100
        assert a.model == "fake-classifier-1" and a.prompt_version == "v1" and a.analyzed_at


def test_sync_does_not_analyze_when_auto_analysis_is_off(user, settings):
    settings.AUTO_ANALYZE_ON_IMPORT = False
    account = connect_fake_account(user)
    sync(account)
    assert EmailModel.objects.filter(user=user).exists()
    assert not EmailAnalysisModel.objects.filter(user=user).exists()


@pytest.mark.parametrize("mode", ["invalid_json", "bad_enum", "out_of_range", "timeout"])
def test_failures_are_retried_then_failed_and_nothing_invalid_persisted(user, mode):
    account = connect_fake_account(user)
    set_failure_mode(mode)
    sync(account)  # sync itself succeeds even though AI is failing
    email = EmailModel.objects.filter(user=user).exclude(subject="").first()
    a = EmailAnalysisModel.objects.get(email_id=email.id)
    assert a.status == "FAILED" and a.attempts == 4  # 1 try + 3 retries
    assert a.priority is None and a.reply_urgency is None and a.spam_likelihood is None
    expected = "TIMEOUT" if mode == "timeout" else "INVALID_OUTPUT"
    assert AiUsageLogModel.objects.filter(email_id=email.id, status=expected).count() == 4
    c = APIClient()
    c.force_login(user)
    assert c.get(f"/api/v1/emails/{email.id}").status_code == 200  # still viewable


def test_sync_keeps_working_while_ai_is_failing(user):
    account = connect_fake_account(user)
    set_failure_mode("timeout")
    first = sync(account)
    deliver_new_mail(account)
    second = sync(account)
    assert first.status == "COMPLETED" and second.status == "COMPLETED" and second.imported_count == 3


def test_usage_log_has_tokens_duration_and_no_body(user):
    account = connect_fake_account(user)
    sync(account)
    log = AiUsageLogModel.objects.filter(user=user, status="SUCCESS").first()
    assert log.input_tokens > 0 and log.output_tokens > 0 and log.duration_ms >= 0
    assert log.provider == "fake" and log.model == "fake-classifier-1"
    fields = {f.name for f in AiUsageLogModel._meta.fields}
    assert not fields & {"body", "body_text", "subject", "content", "prompt"}


def test_prompt_injection_email_gets_normal_result_and_no_action(user):
    account = connect_fake_account(user)
    sync(account)
    before = EmailModel.objects.filter(user=user).count()
    e = EmailModel.objects.get(user=user, external_message_id="fake-m030")
    a = EmailAnalysisModel.objects.get(email_id=e.id)
    assert a.status == "COMPLETED" and a.priority != "CRITICAL" and a.reply_urgency < 70
    assert EmailModel.objects.filter(user=user).count() == before  # nothing deleted/forwarded


def test_prompt_version_change_creates_new_current_analysis(user, settings):
    account = connect_fake_account(user)
    sync(account)
    e = EmailModel.objects.get(user=user, external_message_id="fake-m001")
    settings.AI_PROMPT_VERSION = "v2"
    c = APIClient()
    c.force_login(user)
    r = c.post(f"/api/v1/emails/{e.id}/reanalyze")
    assert r.status_code == 202 and r.json()["prompt_version"] == "v2"
    rows = EmailAnalysisModel.objects.filter(email_id=e.id).order_by("id")
    assert [x.prompt_version for x in rows] == ["v1", "v2"] and rows[1].status == "COMPLETED"
    detail = c.get(f"/api/v1/emails/{e.id}").json()
    assert detail["analysis"]["prompt_version"] == "v2"
    # bulk re-analysis command covers the rest
    call_command("reanalyze_emails", verbosity=0)
    assert not EmailAnalysisModel.objects.filter(user=user).exclude(
        email_id__in=EmailAnalysisModel.objects.filter(prompt_version="v2").values("email_id")).exists()


def test_reanalyze_same_version_reruns_and_is_owner_scoped(user, make_user):
    account = connect_fake_account(user)
    sync(account)
    e = EmailModel.objects.filter(user=user).exclude(subject="").first()
    c = APIClient()
    c.force_login(user)
    assert c.post(f"/api/v1/emails/{e.id}/reanalyze").status_code == 202
    assert EmailAnalysisModel.objects.filter(email_id=e.id).count() == 1
    assert EmailAnalysisModel.objects.get(email_id=e.id).status == "COMPLETED"
    other = APIClient()
    other.force_login(make_user(email="eve@example.com"))
    assert other.post(f"/api/v1/emails/{e.id}/reanalyze").status_code == 404


def test_failed_analysis_can_be_reanalyzed_after_provider_recovers(user):
    account = connect_fake_account(user)
    set_failure_mode("bad_enum")
    sync(account)
    e = EmailModel.objects.filter(user=user).exclude(subject="").first()
    set_failure_mode("none")
    c = APIClient()
    c.force_login(user)
    c.post(f"/api/v1/emails/{e.id}/reanalyze")
    assert EmailAnalysisModel.objects.get(email_id=e.id).status == "COMPLETED"


def test_stale_pending_analyses_are_requeued(db):
    from email_intelligence.infrastructure.tasks import requeue_stale_analyses

    call_command("seed_demo", verbosity=0)
    EmailAnalysisModel.objects.filter(status="PENDING").update(
        updated_at="2020-01-01T00:00:00Z")
    assert requeue_stale_analyses() >= 2
    assert not EmailAnalysisModel.objects.filter(status="PENDING").exists()


def test_demo_failure_mode_endpoint(user):
    c = APIClient()
    c.force_login(user)
    assert c.post("/api/v1/demo/ai/failure-mode", {"mode": "timeout"}, format="json").json() == {"mode": "timeout"}
    assert c.get("/api/v1/demo/ai/failure-mode").json()["mode"] == "timeout"
    assert c.post("/api/v1/demo/ai/failure-mode", {"mode": "explode"}, format="json").status_code == 400


def test_configuration_error_fails_immediately_without_retries(user, settings):
    from unittest import mock

    from email_intelligence.application.ports import AIConfigurationError

    account = connect_fake_account(user)
    with mock.patch("email_intelligence.infrastructure.ai.fake.FakeClassifier.classify",
                    side_effect=AIConfigurationError("Jev AI rejected the API key (401)")):
        sync(account)
    email = EmailModel.objects.filter(user=user).exclude(subject="").first()
    a = EmailAnalysisModel.objects.get(email_id=email.id)
    assert a.status == "FAILED" and a.attempts == 1 and "401" in a.error
    assert AiUsageLogModel.objects.filter(email_id=email.id, status="CONFIG_ERROR").count() == 1


def test_model_version_is_persisted(user):
    account = connect_fake_account(user)
    sync(account)
    a = EmailAnalysisModel.objects.filter(user=user, status="COMPLETED").first()
    assert a.model == "fake-classifier-1" and a.model_version == "fake-classifier-1"


def test_full_pipeline_with_jev_ai_provider(user, settings):
    """AI_PROVIDER=jev_ai end to end (sync → EmailImported → analyze) against a mocked System One."""
    import httpx
    import respx

    settings.AI_PROVIDER = "jev_ai"
    settings.JEV_AI_API_KEY = "sk_test"
    settings.JEV_AI_MODEL = "jev-latest"
    settings.JEV_AI_BASE_URL = "https://thejevai.com/v1/systemone"
    body = {"model": "jev-1.13.0", "usage": {"input_tokens": 300, "output_tokens": 20}, "answers": {
        "priority": {"type": "choice", "choice": "NORMAL", "probabilities": {"NORMAL": 0.7}},
        "category": {"type": "choice", "choice": "WORK", "probabilities": {"WORK": 0.8}},
        "spam": {"type": "noul", "noul": 0.12},
        "reply_urgency": {"type": "score", "score": 2.0},
        "sentiment": {"type": "choice", "choice": "NEUTRAL", "probabilities": {"NEUTRAL": 0.9}}}}
    account = connect_fake_account(user)
    with respx.mock(assert_all_called=True) as m:
        route = m.post("https://thejevai.com/v1/systemone").mock(return_value=httpx.Response(200, json=body))
        sync(account)
    completed = EmailAnalysisModel.objects.filter(user=user, status="COMPLETED")
    assert completed.count() == EmailModel.objects.filter(user=user).count() - 1  # empty email skipped
    a = completed.first()
    assert (a.model, a.model_version, a.spam_likelihood, a.reply_urgency) == ("jev-latest", "jev-1.13.0", 12, 50)
    assert route.call_count == completed.count()
    log = AiUsageLogModel.objects.filter(user=user, status="SUCCESS").first()
    assert log.provider == "jev_ai" and log.model == "jev-1.13.0" and log.input_tokens == 300


def test_full_pipeline_with_openrouter_provider(user, settings):
    """AI_PROVIDER=openrouter selects Jev via OpenRouter's System One endpoint; direct Jev is untouched."""
    import httpx
    import respx

    settings.AI_PROVIDER = "openrouter"
    settings.OPENROUTER_API_KEY = "sk-or-test"
    settings.OPENROUTER_MODEL = "~typesafe/jev-latest"
    settings.OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1/systemone"
    body = {"id": "gen-1", "model": "typesafe/jev-1.13", "usage": {"input_tokens": 900, "output_tokens": 0,
                                                                  "cost": 0.0009}, "answers": {
        "priority": {"type": "choice", "choice": "HIGH", "probabilities": {"HIGH": 0.6}},
        "category": {"type": "choice", "choice": "CUSTOMER", "probabilities": {"CUSTOMER": 0.8}},
        "spam": {"type": "noul", "noul": 0.02},
        "reply_urgency": {"type": "score", "score": 3.0},
        "sentiment": {"type": "choice", "choice": "NEGATIVE", "probabilities": {"NEGATIVE": 0.7}}}}
    account = connect_fake_account(user)
    with respx.mock(assert_all_called=False) as m:
        m.post("https://openrouter.ai/api/v1/systemone").mock(return_value=httpx.Response(200, json=body))
        direct = m.post("https://thejevai.com/v1/systemone")
        sync(account)
        assert not direct.called
    a = EmailAnalysisModel.objects.filter(user=user, status="COMPLETED").first()
    assert (a.model, a.model_version, a.priority, a.reply_urgency) == (
        "~typesafe/jev-latest", "typesafe/jev-1.13", "HIGH", 75)
    log = AiUsageLogModel.objects.filter(user=user, status="SUCCESS").first()
    assert log.provider == "openrouter" and log.input_tokens == 900


def test_duplicate_analyze_jobs_are_harmless(user):
    """Atomic claim: a re-enqueued/duplicate job for the same analysis does no extra AI call."""
    from email_intelligence.infrastructure import container as ei
    from shared_kernel.infrastructure.event_bus import event_bus

    account = connect_fake_account(user)
    with event_bus.muted():
        sync(account)  # import without triggering analysis
    e = EmailModel.objects.filter(user=user).exclude(subject="").first()
    with event_bus.muted():
        a = ei.request_analysis()(email_id=e.id)  # PENDING (enqueue happens on commit → eager)
    a = EmailAnalysisModel.objects.get(pk=a.id)
    if a.status == "PENDING":
        ei.analyze_email()(analysis_id=a.id, final_attempt=False)
    calls = AiUsageLogModel.objects.filter(email_id=e.id).count()
    ei.analyze_email()(analysis_id=a.id, final_attempt=False)  # duplicate job
    assert AiUsageLogModel.objects.filter(email_id=e.id).count() == calls == 1
    assert EmailAnalysisModel.objects.get(pk=a.id).attempts == 1
