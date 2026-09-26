"""Composition root: builds Identity use cases with Django adapters."""

from django.conf import settings

from identity.application import use_cases as uc

from .adapters import DjangoCredentialStore, DjangoEmailNotifier, DjangoPasswordResetTokens
from .persistence.repositories import DjangoUserRepository


def register_user() -> uc.RegisterUser:
    return uc.RegisterUser(DjangoUserRepository(), DjangoCredentialStore())


def authenticate_user() -> uc.AuthenticateUser:
    return uc.AuthenticateUser(DjangoCredentialStore())


def request_password_reset() -> uc.RequestPasswordReset:
    return uc.RequestPasswordReset(DjangoUserRepository(), DjangoPasswordResetTokens(),
                                   DjangoEmailNotifier(), settings.FRONTEND_URL)


def confirm_password_reset() -> uc.ConfirmPasswordReset:
    return uc.ConfirmPasswordReset(DjangoUserRepository(), DjangoPasswordResetTokens(),
                                   DjangoCredentialStore())


def change_password() -> uc.ChangePassword:
    return uc.ChangePassword(DjangoUserRepository(), DjangoCredentialStore())


def update_profile() -> uc.UpdateProfile:
    return uc.UpdateProfile(DjangoUserRepository())
