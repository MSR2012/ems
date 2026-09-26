from __future__ import annotations

from typing import Protocol

from .user import User


class UserRepository(Protocol):
    def get(self, user_id: int) -> User | None: ...

    def get_by_email(self, email: str) -> User | None: ...

    def save(self, user: User) -> User: ...
