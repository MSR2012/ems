import pytest

from email_intelligence.domain.classifications import (
    AnalysisResult,
    AnalysisStatus,
    Category,
    Percentage,
    Priority,
    Sentiment,
)
from email_intelligence.domain.email_analysis import EmailAnalysis
from email_intelligence.domain.events import EmailAnalysisCompleted, EmailAnalysisFailed
from shared_kernel.domain import InvalidStateTransition, InvariantViolation, UserId


def result():
    return AnalysisResult(priority=Priority.HIGH, priority_confidence=Percentage(82),
                          spam_likelihood=Percentage(4), reply_urgency=Percentage(91),
                          category=Category.CUSTOMER, sentiment=Sentiment.NEUTRAL)


def analysis():
    a = EmailAnalysis.request(email_id=1, user_id=UserId(1), model="fake", prompt_version="v1")
    a.id = 3
    return a


def test_lifecycle_pending_running_completed():
    a = analysis()
    assert a.status == AnalysisStatus.PENDING
    a.start()
    a.complete(result())
    assert a.status == AnalysisStatus.COMPLETED and a.analyzed_at and a.attempts == 1
    assert isinstance(a.pull_events()[0], EmailAnalysisCompleted)


def test_failed_is_retryable():
    a = analysis()
    a.start()
    a.fail("invalid output")
    assert isinstance(a.pull_events()[0], EmailAnalysisFailed)
    a.start()
    a.complete(result())
    assert a.status == AnalysisStatus.COMPLETED and a.attempts == 2


def test_release_for_retry_goes_back_to_pending():
    a = analysis()
    a.start()
    a.release_for_retry("timeout")
    assert a.status == AnalysisStatus.PENDING and a.error == "timeout"


def test_completed_cannot_restart_without_explicit_rerun():
    a = analysis()
    a.start()
    a.complete(result())
    with pytest.raises(InvalidStateTransition):
        a.start()


def test_cannot_complete_without_running():
    with pytest.raises(InvalidStateTransition):
        analysis().complete(result())


def test_skip_from_pending():
    a = analysis()
    a.skip("empty body")
    assert a.status == AnalysisStatus.SKIPPED


def test_result_requires_enum_and_percentage_types():
    with pytest.raises(InvariantViolation):
        AnalysisResult(priority="HIGH", priority_confidence=Percentage(1),  # type: ignore[arg-type]
                       spam_likelihood=Percentage(1), reply_urgency=Percentage(1),
                       category=Category.WORK)
    with pytest.raises(InvariantViolation):
        AnalysisResult(priority=Priority.HIGH, priority_confidence=Percentage(1),
                       spam_likelihood=5, reply_urgency=Percentage(1),  # type: ignore[arg-type]
                       category=Category.WORK)


def test_reset_for_rerun_reopens_completed():
    a = analysis()
    a.start()
    a.complete(result())
    a.reset_for_rerun()
    assert a.status == AnalysisStatus.PENDING and a.result is None and a.attempts == 0
