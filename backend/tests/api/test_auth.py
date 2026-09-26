import re

import pytest
from django.core import mail
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db

PW = "Sup3r-Secret-pw"


def csrf_client():
    """Client that enforces CSRF like a browser; fetches the cookie via /auth/csrf."""
    c = APIClient(enforce_csrf_checks=True)
    c.get("/api/v1/auth/csrf")
    return c, c.cookies["csrftoken"].value


def test_csrf_endpoint_sets_cookie():
    c = APIClient()
    r = c.get("/api/v1/auth/csrf")
    assert r.status_code == 200 and "csrftoken" in r.cookies


def test_register_logs_in_and_returns_profile():
    c, token = csrf_client()
    r = c.post("/api/v1/auth/register", {"name": "Bob", "email": "Bob@Example.com", "password": PW},
               format="json", HTTP_X_CSRFTOKEN=token)
    assert r.status_code == 201, r.content
    assert r.json()["email"] == "bob@example.com"
    assert "password" not in r.json()
    me = c.get("/api/v1/me")
    assert me.status_code == 200 and me.json()["name"] == "Bob"
    assert me.json()["settings"]["spam_threshold_percent"] == 70


def test_register_validation_errors_are_field_level(user):
    c, token = csrf_client()
    r = c.post("/api/v1/auth/register", {"email": user.email, "password": "123"}, format="json",
               HTTP_X_CSRFTOKEN=token)
    assert r.status_code == 400
    body = r.json()
    assert "email" in body and "password" in body


def test_login_logout_login(user):
    c, token = csrf_client()
    r = c.post("/api/v1/auth/login", {"email": "ALICE@example.com", "password": PW}, format="json",
               HTTP_X_CSRFTOKEN=token)
    assert r.status_code == 200, r.content
    token = c.cookies["csrftoken"].value  # rotated on login
    assert c.get("/api/v1/me").status_code == 200
    assert c.post("/api/v1/auth/logout", HTTP_X_CSRFTOKEN=token).status_code == 204
    assert c.get("/api/v1/me").status_code == 401


def test_login_wrong_password(user):
    c, token = csrf_client()
    r = c.post("/api/v1/auth/login", {"email": user.email, "password": "nope"}, format="json",
               HTTP_X_CSRFTOKEN=token)
    assert r.status_code == 400 and r.json()["detail"] == "Invalid email or password."


@pytest.mark.parametrize("path", ["/api/v1/auth/login", "/api/v1/auth/register",
                                  "/api/v1/auth/password-reset"])
def test_public_unsafe_endpoints_require_csrf(path, user):
    c = APIClient(enforce_csrf_checks=True)
    r = c.post(path, {"email": user.email, "password": PW}, format="json")
    assert r.status_code == 403


def test_authenticated_unsafe_requests_require_csrf(user):
    c = APIClient(enforce_csrf_checks=True)
    c.force_login(user)
    assert c.patch("/api/v1/me", {"name": "X"}, format="json").status_code == 403
    assert c.post("/api/v1/auth/logout").status_code == 403


@pytest.mark.parametrize("method,path", [
    ("get", "/api/v1/me"), ("patch", "/api/v1/me"), ("post", "/api/v1/auth/logout"),
    ("post", "/api/v1/me/password"),
])
def test_protected_endpoints_return_401_without_session(method, path):
    r = getattr(APIClient(), method)(path)
    assert r.status_code == 401


def test_password_reset_flow(user):
    c, token = csrf_client()
    r = c.post("/api/v1/auth/password-reset", {"email": user.email}, format="json",
               HTTP_X_CSRFTOKEN=token)
    assert r.status_code == 200
    assert len(mail.outbox) == 1
    link = re.search(r"http\S+", mail.outbox[0].body).group(0)
    assert "/password-reset/confirm?uid=" in link
    uid = re.search(r"uid=([^&]+)", link).group(1)
    tok = re.search(r"token=(\S+)", link).group(1)
    new_pw = "Brand-New-pass-42"
    r = c.post("/api/v1/auth/password-reset/confirm",
               {"uid": uid, "token": tok, "new_password": new_pw}, format="json",
               HTTP_X_CSRFTOKEN=token)
    assert r.status_code == 200, r.content
    # old password no longer works, new one does; token is single-use
    assert c.post("/api/v1/auth/login", {"email": user.email, "password": PW}, format="json",
                  HTTP_X_CSRFTOKEN=token).status_code == 400
    r = c.post("/api/v1/auth/password-reset/confirm",
               {"uid": uid, "token": tok, "new_password": "Another-pass-43"}, format="json",
               HTTP_X_CSRFTOKEN=token)
    assert r.status_code == 400 and "token" in r.json()
    assert c.post("/api/v1/auth/login", {"email": user.email, "password": new_pw}, format="json",
                  HTTP_X_CSRFTOKEN=token).status_code == 200


def test_password_reset_unknown_email_does_not_leak():
    c, token = csrf_client()
    r = c.post("/api/v1/auth/password-reset", {"email": "nobody@example.com"}, format="json",
               HTTP_X_CSRFTOKEN=token)
    assert r.status_code == 200 and len(mail.outbox) == 0


def test_update_profile_and_change_password(auth_client, user):
    r = auth_client.patch("/api/v1/me", {"name": "Alice Cooper"}, format="json")
    assert r.status_code == 200 and r.json()["name"] == "Alice Cooper"
    r = auth_client.post("/api/v1/me/password", {"current_password": "wrong", "new_password": "x"},
                         format="json")
    assert r.status_code == 400 and "current_password" in r.json()
    r = auth_client.post("/api/v1/me/password",
                         {"current_password": PW, "new_password": "Changed-pass-99"}, format="json")
    assert r.status_code == 200
    assert auth_client.get("/api/v1/me").status_code == 200  # session kept
    user.refresh_from_db()
    assert user.check_password("Changed-pass-99")


def test_health_is_public():
    r = APIClient().get("/api/v1/health")
    assert r.status_code in (200, 503)
    assert set(r.json()["checks"]) == {"database", "redis", "celery"}


def test_session_endpoint_is_public(user):
    c = APIClient()
    r = c.get("/api/v1/auth/session")
    assert r.status_code == 200 and r.json() == {"authenticated": False, "user": None}
    c.force_login(user)
    r = c.get("/api/v1/auth/session")
    assert r.json()["authenticated"] and r.json()["user"]["email"] == user.email
