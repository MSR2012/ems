import pytest

from email_intelligence.domain.classifications import Percentage, Priority, Thresholds
from shared_kernel.domain import InvariantViolation


@pytest.mark.parametrize("value", [0, 1, 50, 99, 100])
def test_percentage_accepts_0_to_100(value):
    assert Percentage(value).value == value


@pytest.mark.parametrize("value", [-1, 101, 1000])
def test_percentage_rejects_out_of_range(value):
    with pytest.raises(InvariantViolation):
        Percentage(value)


@pytest.mark.parametrize("value", [50.5, "50", True, None])
def test_percentage_rejects_non_integers(value):
    with pytest.raises(InvariantViolation):
        Percentage(value)


def test_percentage_ordering_and_threshold():
    assert Percentage(70).at_least(70)
    assert not Percentage(69).at_least(Percentage(70))
    assert Percentage(10) < Percentage(20)
    assert str(Percentage(42)) == "42%"


def test_thresholds_are_inclusive_and_configurable():
    t = Thresholds.of(spam=70, urgency=80)
    assert t.is_potential_spam(70) and not t.is_potential_spam(69)
    assert t.is_high_urgency(80) and not t.is_high_urgency(79)
    assert not t.is_potential_spam(None)


def test_priority_rank():
    assert Priority.CRITICAL.rank > Priority.HIGH.rank > Priority.NORMAL.rank > Priority.LOW.rank
    assert Priority.HIGH.is_high_or_critical and not Priority.NORMAL.is_high_or_critical
