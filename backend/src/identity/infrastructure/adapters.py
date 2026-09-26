from __future__ import annotations

from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from identity.domain.user import User

from .persistence.models import UserModel
from .persistence.repositories import to_domain


class DjangoCredentialStore:
    def create_user(self, *, email: str, name: str, password: str) -> User:
        return to_domain(UserModel.objects.create_user(email=email, name=name, password=password))

    def verify(self, email: str, password: str) -> User | None:
        m = authenticate(username=email, password=password)
        return to_domain(m) if m is not None else None

    def set_password(self, user_id: int, password: str) -> None:
        m = UserModel.objects.get(pk=user_id)
        m.set_password(password)
        m.save(update_fields=["password"])

    def check_password(self, user_id: int, password: str) -> bool:
        m = UserModel.objects.filter(pk=user_id).first()
        return bool(m and m.check_password(password))

    def password_problems(self, password: str, *, email: str = "", name: str = "") -> list[str]:
        try:
            validate_password(password or "", user=UserModel(email=email, name=name))
        except ValidationError as exc:
            return list(exc.messages)
        return []


class DjangoPasswordResetTokens:
    def make(self, user_id: int) -> tuple[str, str]:
        m = UserModel.objects.get(pk=user_id)
        return urlsafe_base64_encode(force_bytes(m.pk)), default_token_generator.make_token(m)

    def resolve(self, uid: str, token: str) -> int | None:
        try:
            pk = int(force_str(urlsafe_base64_decode(uid)))
        except (TypeError, ValueError, OverflowError):
            return None
        m = UserModel.objects.filter(pk=pk).first()
        if m is None or not default_token_generator.check_token(m, token):
            return None
        return m.pk


class DjangoEmailNotifier:
    def send_password_reset(self, *, to: str, name: str, link: str) -> None:
        greeting = f"Hi {name}," if name else "Hi,"
        send_mail(
            subject="Reset your Inbox AI password",
            message=(f"{greeting}\n\nUse the link below to set a new password:\n\n{link}\n\n"
                     "If you did not request this, you can ignore this email.\n"),
            from_email=None,
            recipient_list=[to],
        )
