from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from shared_kernel.domain import InvariantViolation, ValueObject


@dataclass(frozen=True)
class OAuthCredentials(ValueObject):
    """OAuth tokens. Plaintext only in memory; persisted as ciphertext via TokenCipher."""

    access_token: str = field(repr=False)
    refresh_token: str = field(repr=False)
    expires_at: datetime | None = None
    scopes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.access_token:
            raise InvariantViolation("access token is required")

    def is_expired(self, now: datetime, leeway: timedelta = timedelta(seconds=60)) -> bool:
        return self.expires_at is not None and self.expires_at - leeway <= now

    def refreshed(self, access_token: str, expires_at: datetime | None,
                  refresh_token: str | None = None) -> OAuthCredentials:
        return OAuthCredentials(
            access_token=access_token,
            refresh_token=refresh_token or self.refresh_token,
            expires_at=expires_at,
            scopes=self.scopes,
        )


@dataclass(frozen=True)
class HistoryId(ValueObject):
    """Gmail mailbox history cursor (monotonically increasing unsigned integer as string)."""

    value: str

    def __post_init__(self) -> None:
        if not str(self.value).isdigit():
            raise InvariantViolation("history id must be numeric")

    def __str__(self) -> str:
        return str(self.value)

    def is_newer_than(self, other: HistoryId | None) -> bool:
        return other is None or int(self.value) > int(other.value)
