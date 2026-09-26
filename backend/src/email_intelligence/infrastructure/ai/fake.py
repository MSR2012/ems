"""Demo-mode classifier: deterministic, schema-valid analyses via the same validation path,
with configurable failures (set through POST /api/v1/demo/ai/failure-mode)."""

from __future__ import annotations

import json
import time

import redis
from django.conf import settings

from email_intelligence.application.ports import (
    AIInvalidOutput,
    AITimeout,
    ClassificationOutcome,
    ClassificationRequest,
)

from . import fake_rules
from .config import FAKE_MODEL
from .prompts import state
from .schema import OutputValidationError, parse_output

FAILURE_KEY = "demo:ai_failure_mode"
FAILURE_MODES = ("none", "invalid_json", "bad_enum", "out_of_range", "timeout")


def _redis():
    return redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)


def get_failure_mode() -> str:
    try:
        return _redis().get(FAILURE_KEY) or "none"
    except redis.RedisError:
        return "none"


def set_failure_mode(mode: str) -> None:
    if mode not in FAILURE_MODES:
        raise ValueError(mode)
    if mode == "none":
        _redis().delete(FAILURE_KEY)
    else:
        _redis().set(FAILURE_KEY, mode)


class FakeClassifier:
    provider = "fake"
    model = FAKE_MODEL

    def __init__(self, latency_ms: int | None = None) -> None:
        self._latency = (latency_ms if latency_ms is not None
                         else getattr(settings, "FAKE_AI_LATENCY_MS", 0)) / 1000

    def classify(self, request: ClassificationRequest) -> ClassificationOutcome:
        if self._latency:
            time.sleep(self._latency)
        tin = len(json.dumps(state(request))) // 4 + 180  # rough token estimate incl. questions
        mode = get_failure_mode()
        if mode == "timeout":
            raise AITimeout("simulated AI provider timeout", input_tokens=tin)
        raw = fake_rules.classify(request.subject, request.body, request.sender)
        if mode == "bad_enum":
            raw["priority"] = "URGENTISH"
        elif mode == "out_of_range":
            raw["reply_urgency"] = 140
        text = "{not valid json" if mode == "invalid_json" else json.dumps(raw)
        tout = len(text) // 4
        try:
            result = parse_output(text)
        except OutputValidationError as exc:
            raise AIInvalidOutput(str(exc), input_tokens=tin, output_tokens=tout) from exc
        return ClassificationOutcome(result=result, input_tokens=tin, output_tokens=tout,
                                     model_version=FAKE_MODEL)
