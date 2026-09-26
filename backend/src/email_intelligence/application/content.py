"""Content preparation for classification (§9 steps 2–5), pure Python.

- normalize whitespace / line endings
- drop quoted history ("> ..." lines, "On … wrote:" blocks, forwarded headers)
- drop signatures (after a "-- " delimiter)
- apply a character budget (≈ token limit)
"""

from __future__ import annotations

import re

_QUOTE_HEADER = re.compile(r"^\s*(On .{0,200}wrote:|-{2,}\s*Original Message\s*-{2,}|From: .+ Sent: .+)\s*$",
                           re.IGNORECASE)
_SIGNATURE = re.compile(r"^\s*--\s*$")


def strip_quotes_and_signature(text: str) -> str:
    out: list[str] = []
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if _SIGNATURE.match(line) or _QUOTE_HEADER.match(line):
            break
        if line.lstrip().startswith(">"):
            continue
        out.append(line)
    cleaned = "\n".join(out)
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


def prepare(subject: str, body: str, max_chars: int) -> tuple[str, str, bool]:
    """Returns (subject, body, truncated)."""
    subject = " ".join((subject or "").split())[:500]
    body = strip_quotes_and_signature(body or "")
    body = re.sub(r"[ \t ]+", " ", body)
    truncated = len(body) > max_chars
    if truncated:
        body = body[:max_chars].rsplit(" ", 1)[0] + " …[truncated]"
    return subject, body, truncated
