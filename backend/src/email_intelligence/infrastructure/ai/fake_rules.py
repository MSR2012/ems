"""Deterministic keyword heuristics used by the demo-mode fake classifier.

Produces schema-shaped raw output (same shape the Jev AI adapter produces), so it goes through
the exact same validation path. Deterministic: the same input always yields the same output.
Note: it deliberately ignores imperative instructions inside the email (prompt injection) —
it only scores content signals.
"""

from __future__ import annotations

import hashlib
import re

_CATEGORY_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("NEWSLETTER", ("newsletter", "digest", "issue #", "weekly #", "morning brief")),
    ("MARKETING", ("flash sale", "% off", "free shipping", "new arrivals", "promo", "deal")),
    ("SOCIAL", ("linkedin", "commented on", "liked", "connection request", "meetup")),
    ("TRANSACTION", ("receipt", "has shipped", "order #", "trip receipt", "ticket and qr")),
    ("FINANCE", ("invoice", "payment", "statement", "tax", "refund", "charged", "bank")),
    ("SUPPORT", ("ticket #", "support request", "helpdesk", "support team")),
    ("CUSTOMER", ("outage", "our users", "our customers", "escalat", "integration is blocked",
                  "our integration", "my subscription", "acme", "renewal")),
    ("SALES", ("proposal", "contract", "demos", "sales pipeline", "enterprise plan", "outbound")),
    ("NOTIFICATION", ("notification", "security alert", "reminder", "ci failed", "review requested",
                      "shared a page", "sign-in", "no action required")),
    ("PERSONAL", ("mom", "dinner", "photos", "lunch", "love,", "trip", "sweetie")),
    ("WORK", ("board deck", "design review", "meeting", "all-hands", "deadline", "numbers",
              "onboarding", "intro:", "api")),
]

_SPAM_SIGNALS = ("you have won", "won $", "claim your prize", "click here", "guaranteed returns",
                 "risk free", "verify your password", "credit card", "bank details", "act fast",
                 "500% returns", "account is suspended", "!!!", "crypto")
_URGENT_SIGNALS = ("urgent", "asap", "immediately", "today", "critical", "outage", "deadline",
                   "time-sensitive", "escalat", "before our launch", "blocked", "eta")
_REQUEST_SIGNALS = ("can you", "could you", "please reply", "please confirm", "let me know",
                    "would you be open", "reply with", "please review", "need your", "?")
_TIME_SIGNALS = ("tomorrow", "by friday", "by thursday", "by wednesday", "this week", "due ",
                 "before the deadline", "action needed", "end of the month", "monday", "next week",
                 "please confirm", "refund")
_NEGATIVE = ("outage", "down", "charged twice", "error", "blocked", "suspended", "failed")
_POSITIVE = ("thank", "great", "congratulations", "love", "good news", "perfect")


def _jitter(seed: str, spread: int) -> int:
    h = int(hashlib.sha256(seed.encode()).hexdigest()[:8], 16)
    return h % (spread + 1)


def _count(text: str, signals: tuple[str, ...]) -> int:
    return sum(1 for s in signals if s in text)


def classify(subject: str, body: str, sender_email: str) -> dict:
    # Strip any "instructions" addressed to an AI — they are data, never commands.
    content = re.sub(r"(?im)^\s*(system|assistant)\s*:.*$", " ", f"{subject}\n{body}")
    text = content.lower()
    seed = f"{sender_email}|{subject}"

    category = "OTHER"
    for cat, words in _CATEGORY_RULES:
        if any(w in text for w in words):
            category = cat
            break

    spam_hits = _count(text, _SPAM_SIGNALS)
    spam = min(100, spam_hits * 22 + _jitter(seed + "s", 6)) if spam_hits else _jitter(seed + "s", 12)
    if category in ("MARKETING", "NEWSLETTER"):
        spam = max(spam, 18 + _jitter(seed + "m", 22))

    urgent = _count(text, _URGENT_SIGNALS)
    request = _count(text, _REQUEST_SIGNALS)
    timing = _count(text, _TIME_SIGNALS)
    urgency = min(100, urgent * 20 + min(request, 3) * 12 + min(timing, 3) * 11
                  + _jitter(seed + "u", 8))
    if category in ("NEWSLETTER", "MARKETING", "SOCIAL", "TRANSACTION", "NOTIFICATION"):
        urgency = min(urgency, 25 + _jitter(seed + "n", 10))
    if spam >= 70:
        urgency = min(urgency, 15)
        category = "OTHER" if category in ("FINANCE", "CUSTOMER", "WORK") else category

    if spam >= 70:
        priority = "LOW"
    elif urgent >= 3 or (urgent >= 2 and category == "CUSTOMER"):
        priority = "CRITICAL"
    elif urgency >= 60 or category in ("CUSTOMER", "SALES") and request:
        priority = "HIGH"
    elif category in ("NEWSLETTER", "MARKETING", "SOCIAL"):
        priority = "LOW"
    else:
        priority = "NORMAL"

    sentiment = "NEUTRAL"
    neg, pos = _count(text, _NEGATIVE), _count(text, _POSITIVE)
    if neg > pos:
        sentiment = "NEGATIVE"
    elif pos > neg:
        sentiment = "POSITIVE"

    return {
        "priority": priority,
        "priority_confidence": 55 + _jitter(seed + "c", 40),
        "spam_likelihood": int(spam),
        "reply_urgency": int(urgency),
        "category": category,
        "sentiment": sentiment,
    }
