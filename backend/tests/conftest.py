import pytest
from rest_framework.test import APIClient


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def make_user(db):
    from identity.infrastructure.persistence.models import UserModel

    def _make(email="alice@example.com", password="Sup3r-Secret-pw", name="Alice"):
        return UserModel.objects.create_user(email=email, password=password, name=name)

    return _make


@pytest.fixture
def user(make_user):
    return make_user()


@pytest.fixture
def auth_client(user):
    client = APIClient()
    client.force_login(user)
    return client
