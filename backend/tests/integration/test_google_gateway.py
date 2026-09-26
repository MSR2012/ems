"""Real Gmail adapter against mocked Google HTTP endpoints (respx)."""

import base64

import httpx
import pytest
import respx

from gmail_integration.application.ports import (
    AccessContext,
    GmailAuthError,
    GmailRateLimitError,
    GmailTokenExpired,
    GmailUnavailableError,
    HistoryExpiredError,
)
from gmail_integration.infrastructure.gmail.google_gateway import (
    GMAIL,
    TOKEN_URL,
    USERINFO_URL,
    GoogleGmailGateway,
)

CTX = AccessContext(access_token="at", refresh_token="rt", expires_at=None, google_account_id="g")


def b64(s: str) -> str:
    return base64.urlsafe_b64encode(s.encode()).decode().rstrip("=")


@pytest.fixture
def gw(settings):
    settings.GOOGLE_OAUTH_CLIENT_ID = "cid"
    settings.GOOGLE_OAUTH_CLIENT_SECRET = "secret"
    settings.GOOGLE_OAUTH_REDIRECT_URI = "http://localhost:5173/api/v1/integrations/gmail/callback"
    settings.GMAIL_SCOPES = ["openid", "email", "https://www.googleapis.com/auth/gmail.readonly"]
    return GoogleGmailGateway(httpx.Client())


def test_authorization_url_requests_minimal_readonly_scope_offline(gw):
    url = gw.authorization_url("st4te")
    assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert "gmail.readonly" in url and "access_type=offline" in url and "state=st4te" in url
    assert "gmail.modify" not in url and "mail.google.com" not in url


@respx.mock
def test_exchange_code_and_identity(gw):
    route = respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json={
        "access_token": "AT", "refresh_token": "RT", "expires_in": 3599, "scope": "openid email"}))
    respx.get(USERINFO_URL).mock(return_value=httpx.Response(200, json={"sub": "123", "email": "a@gmail.com"}))
    grant = gw.exchange_code("the-code")
    assert grant.access_token == "AT" and grant.refresh_token == "RT" and grant.expires_at
    assert b"code=the-code" in route.calls[0].request.content
    ident = gw.fetch_identity(grant)
    assert ident.google_account_id == "123" and ident.email == "a@gmail.com"


@respx.mock
def test_refresh_invalid_grant_means_revoked(gw):
    respx.post(TOKEN_URL).mock(return_value=httpx.Response(400, json={"error": "invalid_grant"}))
    with pytest.raises(GmailAuthError):
        gw.refresh(CTX)


@respx.mock
def test_refresh_success(gw):
    respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json={"access_token": "NEW", "expires_in": 60}))
    assert gw.refresh(CTX).access_token == "NEW"


@respx.mock
def test_list_recent_messages_paginates_with_bounded_query(gw):
    route = respx.get(f"{GMAIL}/messages").mock(return_value=httpx.Response(200, json={
        "messages": [{"id": "m1"}, {"id": "m2"}], "nextPageToken": "p2"}))
    page = gw.list_recent_message_ids(CTX, days=30)
    assert page.message_ids == ["m1", "m2"] and page.next_page_token == "p2"
    q = route.calls[0].request.url.params
    assert q["q"] == "newer_than:30d" and q["labelIds"] == "INBOX"
    assert route.calls[0].request.headers["Authorization"] == "Bearer at"


@respx.mock
def test_history_added_messages_and_404_expired(gw):
    respx.get(f"{GMAIL}/history").mock(side_effect=[
        httpx.Response(200, json={"historyId": "900", "history": [
            {"messagesAdded": [{"message": {"id": "a"}}, {"message": {"id": "b"}}]},
            {"messagesAdded": [{"message": {"id": "a"}}]}]}),
        httpx.Response(404, json={"error": {"code": 404}}),
    ])
    page = gw.list_history(CTX, start_history_id="100")
    assert page.added_message_ids == ["a", "b"] and page.history_id == "900"
    with pytest.raises(HistoryExpiredError):
        gw.list_history(CTX, start_history_id="1")


@respx.mock
@pytest.mark.parametrize("resp,exc", [
    (httpx.Response(429, headers={"Retry-After": "7"}), GmailRateLimitError),
    (httpx.Response(403, json={"error": {"errors": [{"reason": "userRateLimitExceeded"}]}}),
     GmailRateLimitError),
    (httpx.Response(401), GmailTokenExpired),
    (httpx.Response(503), GmailUnavailableError),
])
def test_error_mapping(gw, resp, exc):
    respx.get(f"{GMAIL}/profile").mock(return_value=resp)
    with pytest.raises(exc) as info:
        gw.current_history_id(CTX)
    if isinstance(info.value, GmailRateLimitError) and resp.status_code == 429:
        assert info.value.retry_after == 7


@respx.mock
def test_network_error_is_unavailable(gw):
    respx.get(f"{GMAIL}/profile").mock(side_effect=httpx.ConnectError("boom"))
    with pytest.raises(GmailUnavailableError):
        gw.current_history_id(CTX)


@respx.mock
def test_get_message_translates_payload(gw):
    respx.get(f"{GMAIL}/messages/abc").mock(return_value=httpx.Response(200, json={
        "id": "abc", "threadId": "t1", "historyId": "555", "internalDate": "1767225600000",
        "labelIds": ["INBOX", "UNREAD"], "snippet": "Hello there",
        "payload": {
            "mimeType": "multipart/mixed",
            "headers": [
                {"name": "From", "value": "Jane Doe <jane@example.com>"},
                {"name": "To", "value": "me@gmail.com, Bob <bob@example.com>"},
                {"name": "Cc", "value": "carol@example.com"},
                {"name": "Subject", "value": "Quarterly report"},
            ],
            "parts": [
                {"mimeType": "multipart/alternative", "parts": [
                    {"mimeType": "text/plain", "body": {"data": b64("Plain body")}},
                    {"mimeType": "text/html", "body": {"data": b64("<p>HTML body</p>")}},
                ]},
                {"mimeType": "application/pdf", "filename": "report.pdf",
                 "body": {"attachmentId": "att-1", "size": 12345}},
            ],
        },
    }))
    m = gw.get_message(CTX, "abc")
    assert (m.external_message_id, m.external_thread_id, m.history_id) == ("abc", "t1", "555")
    assert m.sender_name == "Jane Doe" and m.sender_email == "jane@example.com"
    assert {r["email"] for r in m.recipients} == {"me@gmail.com", "bob@example.com", "carol@example.com"}
    assert m.subject == "Quarterly report" and m.body_text == "Plain body"
    assert m.body_html == "<p>HTML body</p>" and not m.is_read
    assert m.attachments == [{"external_attachment_id": "att-1", "filename": "report.pdf",
                              "mime_type": "application/pdf", "size": 12345}]
    assert m.received_at.year == 2026
