from datetime import UTC, datetime, timedelta

from email_intelligence.domain.attention_policy import AttentionCandidate, AttentionPolicy
from email_intelligence.domain.classifications import Priority, Thresholds

T0 = datetime(2026, 9, 1, tzinfo=UTC)


def c(i, prio=Priority.NORMAL, urg=0, spam=0, read=False, age=0):
    return AttentionCandidate(email_id=i, priority=prio, reply_urgency=urg, spam_likelihood=spam,
                              is_read=read, received_at=T0 - timedelta(hours=age))


def test_includes_high_urgency_or_high_priority_and_excludes_spam():
    p = AttentionPolicy(Thresholds.of(70, 70))
    assert p.needs_attention(c(1, urg=70))
    assert p.needs_attention(c(2, prio=Priority.HIGH))
    assert p.needs_attention(c(3, prio=Priority.CRITICAL))
    assert not p.needs_attention(c(4, urg=69))
    assert not p.needs_attention(c(5, prio=Priority.CRITICAL, urg=95, spam=70))


def test_ordering_urgency_then_priority_then_unread_then_newest():
    p = AttentionPolicy(Thresholds.of(70, 70))
    items = [
        c(1, prio=Priority.HIGH, urg=80),
        c(2, prio=Priority.CRITICAL, urg=80),
        c(3, prio=Priority.NORMAL, urg=95),
        c(4, prio=Priority.CRITICAL, urg=80, read=True),
        c(5, prio=Priority.CRITICAL, urg=80, age=5),
        c(6, prio=Priority.LOW, urg=10),  # excluded
    ]
    assert [x.email_id for x in p.select(items)] == [3, 2, 5, 4, 1]


def test_threshold_change_changes_selection():
    items = [c(1, urg=75), c(2, urg=85)]
    assert len(AttentionPolicy(Thresholds.of(70, 70)).select(items)) == 2
    assert [x.email_id for x in AttentionPolicy(Thresholds.of(70, 80)).select(items)] == [2]


def test_limit():
    items = [c(i, urg=90) for i in range(10)]
    assert len(AttentionPolicy(Thresholds.of(70, 70)).select(items, limit=3)) == 3
