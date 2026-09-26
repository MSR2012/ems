"""Classification value objects (§8)."""

from __future__ import annotations

import enum
from dataclasses import dataclass

from shared_kernel.domain import InvariantViolation, ValueObject


class Priority(enum.StrEnum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    NORMAL = "NORMAL"
    LOW = "LOW"

    @property
    def rank(self) -> int:
        """Higher = more important (used for ordering)."""
        return {"CRITICAL": 4, "HIGH": 3, "NORMAL": 2, "LOW": 1}[self.value]

    @property
    def is_high_or_critical(self) -> bool:
        return self in (Priority.CRITICAL, Priority.HIGH)


class Category(enum.StrEnum):
    WORK = "WORK"
    PERSONAL = "PERSONAL"
    FINANCE = "FINANCE"
    CUSTOMER = "CUSTOMER"
    SALES = "SALES"
    MARKETING = "MARKETING"
    SOCIAL = "SOCIAL"
    NOTIFICATION = "NOTIFICATION"
    TRANSACTION = "TRANSACTION"
    SUPPORT = "SUPPORT"
    NEWSLETTER = "NEWSLETTER"
    OTHER = "OTHER"


class Sentiment(enum.StrEnum):
    POSITIVE = "POSITIVE"
    NEUTRAL = "NEUTRAL"
    NEGATIVE = "NEGATIVE"


class AnalysisStatus(enum.StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


@dataclass(frozen=True, order=True)
class Percentage(ValueObject):
    """Integer percentage, 0–100 inclusive."""

    value: int

    def __post_init__(self) -> None:
        if isinstance(self.value, bool) or not isinstance(self.value, int):
            raise InvariantViolation("percentage must be an integer")
        if not 0 <= self.value <= 100:
            raise InvariantViolation("percentage must be between 0 and 100")

    def at_least(self, threshold: Percentage | int) -> bool:
        t = threshold.value if isinstance(threshold, Percentage) else threshold
        return self.value >= t

    def __int__(self) -> int:
        return self.value

    def __str__(self) -> str:
        return f"{self.value}%"


@dataclass(frozen=True)
class Thresholds(ValueObject):
    """Configurable product thresholds for derived views (potential spam, high urgency)."""

    spam: Percentage = Percentage(70)
    urgency: Percentage = Percentage(70)

    @classmethod
    def of(cls, spam: int, urgency: int) -> Thresholds:
        return cls(spam=Percentage(int(spam)), urgency=Percentage(int(urgency)))

    def is_potential_spam(self, spam_likelihood: Percentage | int | None) -> bool:
        if spam_likelihood is None:
            return False
        return int(spam_likelihood) >= self.spam.value

    def is_high_urgency(self, reply_urgency: Percentage | int | None) -> bool:
        if reply_urgency is None:
            return False
        return int(reply_urgency) >= self.urgency.value


@dataclass(frozen=True)
class AnalysisResult(ValueObject):
    """A validated classification. Constructed only from schema-validated AI output."""

    priority: Priority
    priority_confidence: Percentage
    spam_likelihood: Percentage
    reply_urgency: Percentage
    category: Category
    sentiment: Sentiment | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.priority, Priority) or not isinstance(self.category, Category):
            raise InvariantViolation("priority/category must be enum members")
        for f in (self.priority_confidence, self.spam_likelihood, self.reply_urgency):
            if not isinstance(f, Percentage):
                raise InvariantViolation("scores must be Percentage values")
