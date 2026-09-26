from __future__ import annotations

from typing import Protocol

from .email import Email


class EmailRepository(Protocol):
    def get(self, email_id: int) -> Email | None: ...

    def get_for_user(self, email_id: int, user_id: int) -> Email | None: ...

    def find_by_external_id(self, mail_account_id: int, external_message_id: str) -> Email | None: ...

    def save(self, email: Email) -> Email: ...
