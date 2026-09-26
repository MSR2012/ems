"""Ports for Email Intelligence (implemented in infrastructure)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from email_intelligence.domain.classifications import AnalysisResult


@dataclass(frozen=True)
class EmailContent:
    email_id: int
    user_id: int
    sender_email: str
    sender_name: str
    subject: str
    body_text: str


@dataclass(frozen=True)
class ClassificationRequest:
    """Prepared, size-limited content. The body is untrusted data, never instructions."""

    sender: str
    subject: str
    body: str
    truncated: bool
    prompt_version: str


@dataclass(frozen=True)
class ClassificationOutcome:
    result: AnalysisResult
    input_tokens: int
    output_tokens: int
    model_version: str | None = None  # concrete version reported by the provider


class AIError(Exception):
    """Base error from an AIClassifier; carries token usage when known."""

    def __init__(self, message: str, *, input_tokens: int = 0, output_tokens: int = 0) -> None:
        super().__init__(message)
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class AIInvalidOutput(AIError):
    """The provider answered, but the output failed schema validation."""


class AITimeout(AIError):
    pass


class AIProviderError(AIError):
    """Rate limit, 5xx, network — transient."""


class AIConfigurationError(AIError):
    """Missing/invalid API key or a request the provider rejects — retrying cannot help."""


class AIClassifier(Protocol):
    provider: str
    model: str

    def classify(self, request: ClassificationRequest) -> ClassificationOutcome: ...


class EmailContentProvider(Protocol):
    """Reads email content from the Mailbox context (read-only)."""

    def get_content(self, email_id: int) -> EmailContent | None: ...


class AnalysisQueue(Protocol):
    def enqueue_analysis(self, analysis_id: int) -> None: ...


class Clock(Protocol):
    def monotonic_ms(self) -> int: ...
