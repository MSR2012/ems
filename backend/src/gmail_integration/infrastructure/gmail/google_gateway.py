"""Real Gmail gateway (Google OAuth 2.0 + Gmail REST API via httpx). Server-side only."""

from __future__ import annotations

from datetime import timedelta
from urllib.parse import urlencode

import httpx
from django.conf import settings
from django.utils import timezone

from gmail_integration.application.dto import (
    GmailIdentity,
    GmailMessagePage,
    HistoryPage,
    ImportableMessage,
    TokenGrant,
)
from gmail_integration.application.ports import (
    AccessContext,
    GmailAuthError,
    GmailError,
    GmailRateLimitError,
    GmailTokenExpired,
    GmailUnavailableError,
    HistoryExpiredError,
)

from .payload import parse_message

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
GMAIL = "https://gmail.googleapis.com/gmail/v1/users/me"


class GoogleGmailGateway:
    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(timeout=20)

    # --- helpers -------------------------------------------------------------------------
    def _raise_for(self, r: httpx.Response, *, history: bool = False) -> None:
        if r.status_code < 400:
            return
        reason = ""
        try:
            err = r.json().get("error", {})
            reason = err.get("errors", [{}])[0].get("reason", "") if isinstance(err, dict) else str(err)
        except Exception:  # noqa: BLE001
            pass
        if r.status_code == 401:
            raise GmailTokenExpired("access token rejected")
        if r.status_code == 429 or (r.status_code == 403 and "RateLimitExceeded" in reason):
            ra = r.headers.get("Retry-After")
            raise GmailRateLimitError(retry_after=int(ra) if ra and ra.isdigit() else None)
        if r.status_code == 404 and history:
            raise HistoryExpiredError("startHistoryId is too old")
        if r.status_code >= 500:
            raise GmailUnavailableError(f"Gmail API error {r.status_code}")
        raise GmailError(f"Gmail API error {r.status_code} {reason}".strip())

    def _get(self, ctx: AccessContext, url: str, params: dict | None = None, *,
             history: bool = False) -> dict:
        try:
            r = self._client.get(url, params=params,
                                 headers={"Authorization": f"Bearer {ctx.access_token}"})
        except httpx.TransportError as exc:
            raise GmailUnavailableError(exc.__class__.__name__) from exc
        self._raise_for(r, history=history)
        return r.json()

    def _token_request(self, data: dict) -> dict:
        try:
            r = self._client.post(TOKEN_URL, data=data)
        except httpx.TransportError as exc:
            raise GmailUnavailableError(exc.__class__.__name__) from exc
        if r.status_code in (400, 401):
            body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
            if body.get("error") in ("invalid_grant", "unauthorized_client", "invalid_client"):
                raise GmailAuthError(body.get("error"))
        self._raise_for(r)
        return r.json()

    @staticmethod
    def _grant(body: dict) -> TokenGrant:
        expires = body.get("expires_in")
        return TokenGrant(access_token=body["access_token"], refresh_token=body.get("refresh_token"),
                          expires_at=timezone.now() + timedelta(seconds=int(expires)) if expires else None,
                          scopes=tuple((body.get("scope") or "").split()))

    # --- OAuth ---------------------------------------------------------------------------
    def authorization_url(self, state: str) -> str:
        params = {
            "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
            "redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URI,
            "response_type": "code",
            "scope": " ".join(settings.GMAIL_SCOPES),
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
            "state": state,
        }
        return f"{AUTH_URL}?{urlencode(params)}"

    def exchange_code(self, code: str) -> TokenGrant:
        return self._grant(self._token_request({
            "grant_type": "authorization_code", "code": code,
            "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
            "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
            "redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URI,
        }))

    def fetch_identity(self, grant: TokenGrant) -> GmailIdentity:
        ctx = AccessContext(access_token=grant.access_token, refresh_token="", expires_at=None,
                            google_account_id="")
        info = self._get(ctx, USERINFO_URL)
        return GmailIdentity(google_account_id=info["sub"], email=info["email"])

    def refresh(self, ctx: AccessContext) -> TokenGrant:
        if not ctx.refresh_token:
            raise GmailAuthError("no refresh token")
        return self._grant(self._token_request({
            "grant_type": "refresh_token", "refresh_token": ctx.refresh_token,
            "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
            "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
        }))

    def revoke(self, ctx: AccessContext) -> None:
        token = ctx.refresh_token or ctx.access_token
        try:
            self._client.post(REVOKE_URL, params={"token": token})
        except httpx.TransportError:
            pass

    # --- mailbox -------------------------------------------------------------------------
    def current_history_id(self, ctx: AccessContext) -> str:
        return str(self._get(ctx, f"{GMAIL}/profile")["historyId"])

    def list_recent_message_ids(self, ctx: AccessContext, *, days: int,
                                page_token: str | None = None) -> GmailMessagePage:
        params = {"q": f"newer_than:{days}d", "labelIds": "INBOX", "maxResults": 100}
        if page_token:
            params["pageToken"] = page_token
        body = self._get(ctx, f"{GMAIL}/messages", params)
        return GmailMessagePage(message_ids=[m["id"] for m in body.get("messages", [])],
                                next_page_token=body.get("nextPageToken"))

    def list_history(self, ctx: AccessContext, *, start_history_id: str,
                     page_token: str | None = None) -> HistoryPage:
        params = {"startHistoryId": start_history_id, "historyTypes": "messageAdded",
                  "labelId": "INBOX", "maxResults": 500}
        if page_token:
            params["pageToken"] = page_token
        body = self._get(ctx, f"{GMAIL}/history", params, history=True)
        added: list[str] = []
        for h in body.get("history", []):
            for item in h.get("messagesAdded", []):
                mid = item.get("message", {}).get("id")
                if mid and mid not in added:
                    added.append(mid)
        return HistoryPage(added_message_ids=added, history_id=str(body.get("historyId", "")),
                           next_page_token=body.get("nextPageToken"))

    def get_message(self, ctx: AccessContext, message_id: str) -> ImportableMessage:
        return parse_message(self._get(ctx, f"{GMAIL}/messages/{message_id}", {"format": "full"}))
