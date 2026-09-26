"""Application schema for AI output (§10). Provider output is validated here BEFORE any domain
object is created: strict enums, strict integers 0–100, nothing else persisted."""

from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, ValidationError

from email_intelligence.domain.classifications import (
    AnalysisResult,
    Category,
    Percentage,
    Priority,
    Sentiment,
)

Pct = StrictInt  # rejects floats, bools and numeric strings


class AIClassificationOutput(BaseModel):
    # Unknown keys (e.g. an injected "action") are ignored — they can never reach the domain.
    model_config = ConfigDict(extra="ignore", frozen=True)

    priority: Literal["CRITICAL", "HIGH", "NORMAL", "LOW"]
    priority_confidence: Pct = Field(ge=0, le=100)
    spam_likelihood: Pct = Field(ge=0, le=100)
    reply_urgency: Pct = Field(ge=0, le=100)
    category: Literal["WORK", "PERSONAL", "FINANCE", "CUSTOMER", "SALES", "MARKETING", "SOCIAL",
                      "NOTIFICATION", "TRANSACTION", "SUPPORT", "NEWSLETTER", "OTHER"]
    sentiment: Literal["POSITIVE", "NEUTRAL", "NEGATIVE"] | None = None

    def to_domain(self) -> AnalysisResult:
        return AnalysisResult(
            priority=Priority(self.priority),
            priority_confidence=Percentage(self.priority_confidence),
            spam_likelihood=Percentage(self.spam_likelihood),
            reply_urgency=Percentage(self.reply_urgency),
            category=Category(self.category),
            sentiment=Sentiment(self.sentiment) if self.sentiment else None,
        )


# JSON schema handed to providers that support structured output.
OUTPUT_JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["priority", "priority_confidence", "spam_likelihood", "reply_urgency", "category",
                 "sentiment"],
    "properties": {
        "priority": {"type": "string", "enum": [p.value for p in Priority]},
        "priority_confidence": {"type": "integer", "minimum": 0, "maximum": 100},
        "spam_likelihood": {"type": "integer", "minimum": 0, "maximum": 100},
        "reply_urgency": {"type": "integer", "minimum": 0, "maximum": 100},
        "category": {"type": "string", "enum": [c.value for c in Category]},
        "sentiment": {"type": "string", "enum": [s.value for s in Sentiment]},
    },
}


class OutputValidationError(ValueError):
    pass


def parse_output(raw: str | dict) -> AnalysisResult:
    """Validate raw provider output (JSON text or dict) → AnalysisResult, or raise."""
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
    except (json.JSONDecodeError, TypeError) as exc:
        raise OutputValidationError("malformed JSON from AI provider") from exc
    if not isinstance(data, dict):
        raise OutputValidationError("AI output must be a JSON object")
    try:
        return AIClassificationOutput.model_validate(data).to_domain()
    except ValidationError as exc:
        fields = ", ".join(sorted({str(e["loc"][0]) for e in exc.errors() if e.get("loc")}))
        raise OutputValidationError(f"AI output failed schema validation ({fields})") from exc
