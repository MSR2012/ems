"""Logging filters: never log email bodies or OAuth / AI tokens (§20.4, §27)."""

from __future__ import annotations

import logging
import re

SENSITIVE_KEYS = {
    "body", "body_text", "body_html", "body_html_sanitized", "html", "text", "content", "snippet",
    "access_token", "refresh_token", "token", "id_token", "password", "authorization",
    "api_key", "jev_ai_api_key", "client_secret", "code", "encrypted_access_token",
    "encrypted_refresh_token", "cookie", "sessionid", "csrftoken",
}
_PATTERNS = [
    (re.compile(r"(?i)bearer\s+[a-z0-9._\-~+/=]+"), "Bearer [REDACTED]"),
    (re.compile(r"gAAAAA[A-Za-z0-9_\-=]{20,}"), "[REDACTED_CIPHERTEXT]"),
    (re.compile(r"\bya29\.[A-Za-z0-9_\-]+"), "[REDACTED_GOOGLE_TOKEN]"),
    (re.compile(r"\b1//[A-Za-z0-9_\-]{20,}"), "[REDACTED_GOOGLE_REFRESH]"),
    (re.compile(r"fake-(?:at|rt)-[^\s'\"|]+(?:\|[A-Za-z0-9_\-]+)?"), "[REDACTED_TOKEN]"),
    (re.compile(r"(?i)((?:access|refresh|id)_token|api_key|client_secret|password)(['\"]?\s*[:=]\s*['\"]?)[^\s'\",&]+"),
     r"\1\2[REDACTED]"),
    (re.compile(r"([?&](?:code|token|access_token)=)[^&\s]+"), r"\1[REDACTED]"),
    # search terms can reveal email content
    (re.compile(r"([?&]q=)[^&\s\"]+"), r"\1[REDACTED]"),
]
_STD_ATTRS = set(logging.LogRecord("x", 0, "x", 0, "x", None, None).__dict__) | {"message", "asctime"}


def redact(text: str) -> str:
    for pattern, repl in _PATTERNS:
        text = pattern.sub(repl, text)
    return text


class SensitiveDataFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:  # noqa: BLE001
            msg = str(record.msg)
        clean = redact(msg)
        if clean != msg or record.args:
            record.msg, record.args = clean, None
        for key in list(record.__dict__):
            if key in _STD_ATTRS:
                continue
            if key == "request" and not isinstance(record.__dict__[key], str):
                del record.__dict__[key]  # raw socket/request objects: noise, may carry data
                continue
            if key.lower() in SENSITIVE_KEYS:
                record.__dict__[key] = "[REDACTED]"
            elif isinstance(record.__dict__[key], str):
                record.__dict__[key] = redact(record.__dict__[key])
        if record.exc_text:
            record.exc_text = redact(record.exc_text)
        return True
