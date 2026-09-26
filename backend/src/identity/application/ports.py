from __future__ import annotations

from typing import Protocol

from identity.domain.user import User


class CredentialStore(Protocol):
    """Password storage/verification (hashing lives in infrastructure)."""

    def create_user(self, *, email: str, name: str, password: str) -> User: ...

    def verify(self, email: str, password: str) -> User | None: ...

    def set_password(self, user_id: int, password: str) -> None: ...

    def check_password(self, user_id: int, password: str) -> bool: ...

    def password_problems(self, password: str, *, email: str = "", name: str = "") -> list[str]: ...


class PasswordResetTokens(Protocol):
    def make(self, user_id: int) -> tuple[str, str]: ...  # (uid, token)

    def resolve(self, uid: str, token: str) -> int | None: ...


class Notifier(Protocol):
    def send_password_reset(self, *, to: str, name: str, link: str) -> None: ...
