"""JevAIClassifier — adapter for the Jev AI System One API (behind the AIClassifier port).

Contract (https://thejevai.com/docs#quickstart):
  POST https://thejevai.com/v1/systemone
  Authorization: Bearer sk_...      Content-Type: application/json
  {"state": <data>, "model": "jev-latest", "questions": {<id>: {type, instructions, criteria}}}
  → {"model": "jev-1.13.0", "answers": {<id>: {type, noul|choice+probabilities|score+legend,
     confidence}}, "usage": {"input_tokens", "output_tokens"}}
  Errors: 401 invalid key, 422 invalid body, 429 rate limited, 529 overloaded.

All Jev specifics stay in this module: answers are translated into the application schema and
then validated by the same strict Pydantic schema as every other provider.
"""

from __future__ import annotations

import httpx
from django.conf import settings

from email_intelligence.application.ports import (
    AIConfigurationError,
    AIInvalidOutput,
    AIProviderError,
    AITimeout,
    ClassificationOutcome,
    ClassificationRequest,
)

from . import prompts
from .schema import OutputValidationError, parse_output


def _answer(answers: dict, key: str, kind: str) -> dict:
    a = answers.get(key)
    if not isinstance(a, dict):
        raise OutputValidationError(f"Jev AI answer '{key}' is missing")
    if a.get("type") not in (None, kind):
        raise OutputValidationError(f"Jev AI answer '{key}' has type {a.get('type')!r}, expected {kind}")
    return a


def _unit(value, key: str) -> float:
    """A number in [0, 1] (bools and strings rejected)."""
    if isinstance(value, bool) or not isinstance(value, int | float) or not 0 <= value <= 1:
        raise OutputValidationError(f"Jev AI value for '{key}' must be a number between 0 and 1")
    return float(value)


def _choice(answers: dict, key: str, options: dict) -> tuple[str, float]:
    a = _answer(answers, key, "choice")
    choice = a.get("choice")
    if choice not in options:  # unknown enum values are rejected, never coerced
        raise OutputValidationError(f"Jev AI chose unknown option {choice!r} for '{key}'")
    probs = a.get("probabilities") or {}
    p = probs.get(choice, a.get("confidence"))
    return choice, _unit(p if p is not None else 0, f"{key}.probability")


def translate(answers: dict, question_set: dict) -> dict:
    """Jev answers → raw application-schema dict (percentages as 0–100 integers)."""
    priority, priority_p = _choice(answers, "priority", question_set["priority"]["criteria"])
    category, _ = _choice(answers, "category", question_set["category"]["criteria"])
    sentiment, _ = _choice(answers, "sentiment", question_set["sentiment"]["criteria"])
    spam = _unit(_answer(answers, "spam", "noul").get("noul"), "spam.noul")

    levels = len(question_set["reply_urgency"]["criteria"])
    score = _answer(answers, "reply_urgency", "score").get("score")
    if isinstance(score, bool) or not isinstance(score, int | float) or not 0 <= score <= levels - 1:
        raise OutputValidationError(f"Jev AI reply_urgency score must be between 0 and {levels - 1}")

    return {
        "priority": priority,
        "priority_confidence": round(priority_p * 100),
        "spam_likelihood": round(spam * 100),
        "reply_urgency": round(score / (levels - 1) * 100),
        "category": category,
        "sentiment": sentiment,
    }


class JevAIClassifier:
    provider = "jev_ai"

    def __init__(self, client: httpx.Client | None = None, *, api_key: str | None = None,
                 url: str | None = None, model: str | None = None,
                 timeout: float | None = None) -> None:
        self.model = model or settings.JEV_AI_MODEL
        self._key = api_key if api_key is not None else settings.JEV_AI_API_KEY
        self._url = url or settings.JEV_AI_BASE_URL
        self._client = client or httpx.Client()
        self._timeout = timeout or settings.AI_REQUEST_TIMEOUT_SECONDS

    def classify(self, request: ClassificationRequest) -> ClassificationOutcome:
        if not self._key:
            raise AIConfigurationError("JEV_AI_API_KEY is not configured")
        question_set = prompts.questions(request.prompt_version)
        body = {"state": prompts.state(request), "model": self.model, "questions": question_set}
        try:
            r = self._client.post(self._url, json=body, timeout=self._timeout,
                                  headers={"Authorization": f"Bearer {self._key}",
                                           "Content-Type": "application/json"})
        except httpx.TimeoutException as exc:
            raise AITimeout("Jev AI request timed out") from exc
        except httpx.TransportError as exc:
            raise AIProviderError(f"Jev AI unreachable ({exc.__class__.__name__})") from exc

        if r.status_code == 401:
            raise AIConfigurationError("Jev AI rejected the API key (401)")
        if r.status_code == 422:
            raise AIConfigurationError("Jev AI rejected the request body (422)")
        if r.status_code in (429, 529) or r.status_code >= 500:
            raise AIProviderError(f"Jev AI busy or unavailable ({r.status_code})")
        if r.status_code >= 400:
            raise AIProviderError(f"Jev AI error ({r.status_code})")

        try:
            payload = r.json()
            usage = payload.get("usage") or {}
            tin, tout = int(usage.get("input_tokens", 0)), int(usage.get("output_tokens", 0))
            answers = payload["answers"]
            version = str(payload.get("model") or "") or None
            if not isinstance(answers, dict):
                raise TypeError("answers must be an object")
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            raise AIInvalidOutput("unexpected Jev AI response shape") from exc
        try:
            result = parse_output(translate(answers, question_set))
        except OutputValidationError as exc:
            raise AIInvalidOutput(str(exc), input_tokens=tin, output_tokens=tout) from exc
        return ClassificationOutcome(result=result, input_tokens=tin, output_tokens=tout,
                                     model_version=version)
