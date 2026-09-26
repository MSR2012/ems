"""Identity use cases: RegisterUser, AuthenticateUser, RequestPasswordReset,
ConfirmPasswordReset, ChangePassword, UpdateProfile."""

from __future__ import annotations

from dataclasses import dataclass

from identity.domain.repositories import UserRepository
from identity.domain.user import User, normalize_email
from shared_kernel.domain import DomainError, InvariantViolation

from .ports import CredentialStore, Notifier, PasswordResetTokens


class ValidationFailed(DomainError):
    def __init__(self, errors: dict[str, list[str]]) -> None:
        super().__init__("validation failed")
        self.errors = errors


class InvalidCredentials(DomainError):
    pass


@dataclass
class RegisterUser:
    users: UserRepository
    credentials: CredentialStore

    def __call__(self, *, email: str, name: str, password: str) -> User:
        errors: dict[str, list[str]] = {}
        try:
            email = normalize_email(email)
        except InvariantViolation:
            errors["email"] = ["Enter a valid email address."]
        if not errors and self.users.get_by_email(email):
            errors["email"] = ["An account with this email already exists."]
        problems = self.credentials.password_problems(password, email=email, name=name)
        if problems:
            errors["password"] = problems
        if len((name or "").strip()) > 150:
            errors["name"] = ["Ensure this field has no more than 150 characters."]
        if errors:
            raise ValidationFailed(errors)
        return self.credentials.create_user(email=email, name=(name or "").strip(), password=password)


@dataclass
class AuthenticateUser:
    credentials: CredentialStore

    def __call__(self, *, email: str, password: str) -> User:
        user = self.credentials.verify((email or "").strip().lower(), password or "")
        if user is None:
            raise InvalidCredentials("Invalid email or password.")
        return user


@dataclass
class RequestPasswordReset:
    users: UserRepository
    tokens: PasswordResetTokens
    notifier: Notifier
    frontend_url: str

    def __call__(self, *, email: str) -> None:
        """Always succeeds silently (no account enumeration)."""
        try:
            email = normalize_email(email)
        except InvariantViolation:
            return
        user = self.users.get_by_email(email)
        if user is None or user.id is None:
            return
        uid, token = self.tokens.make(user.id)
        link = f"{self.frontend_url.rstrip('/')}/password-reset/confirm?uid={uid}&token={token}"
        self.notifier.send_password_reset(to=user.email, name=user.name, link=link)


@dataclass
class ConfirmPasswordReset:
    users: UserRepository
    tokens: PasswordResetTokens
    credentials: CredentialStore

    def __call__(self, *, uid: str, token: str, new_password: str) -> None:
        user_id = self.tokens.resolve(uid, token)
        user = self.users.get(user_id) if user_id else None
        if user is None:
            raise ValidationFailed({"token": ["This reset link is invalid or has expired."]})
        problems = self.credentials.password_problems(new_password, email=user.email, name=user.name)
        if problems:
            raise ValidationFailed({"new_password": problems})
        self.credentials.set_password(user_id, new_password)


@dataclass
class ChangePassword:
    users: UserRepository
    credentials: CredentialStore

    def __call__(self, *, user_id: int, current_password: str, new_password: str) -> None:
        user = self.users.get(user_id)
        if user is None:
            raise ValidationFailed({"detail": ["User not found."]})
        if not self.credentials.check_password(user_id, current_password):
            raise ValidationFailed({"current_password": ["Current password is incorrect."]})
        problems = self.credentials.password_problems(new_password, email=user.email, name=user.name)
        if problems:
            raise ValidationFailed({"new_password": problems})
        self.credentials.set_password(user_id, new_password)


@dataclass
class UpdateProfile:
    users: UserRepository

    def __call__(self, *, user_id: int, name: str | None = None) -> User:
        user = self.users.get(user_id)
        if user is None:
            raise ValidationFailed({"detail": ["User not found."]})
        try:
            user.update_profile(name=name)
        except InvariantViolation as exc:
            raise ValidationFailed({"name": [str(exc)]}) from exc
        return self.users.save(user)
