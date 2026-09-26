from __future__ import annotations

from identity.domain.user import User

from .models import UserModel


def to_domain(m: UserModel) -> User:
    return User(id=m.pk, email=m.email, name=m.name, created_at=m.created_at)


class DjangoUserRepository:
    def get(self, user_id: int) -> User | None:
        m = UserModel.objects.filter(pk=user_id).first()
        return to_domain(m) if m else None

    def get_by_email(self, email: str) -> User | None:
        m = UserModel.objects.filter(email__iexact=email).first()
        return to_domain(m) if m else None

    def save(self, user: User) -> User:
        if user.id is None:
            m = UserModel.objects.create_user(email=user.email, name=user.name)
            user.id = m.pk
        else:
            UserModel.objects.filter(pk=user.id).update(name=user.name, email=user.email)
        return user
