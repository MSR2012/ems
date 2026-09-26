"""ACL translator for real Gmail API message resources (format=full) → ImportableMessage."""

from __future__ import annotations

import base64
from datetime import UTC, datetime
from email.utils import getaddresses, parseaddr, parsedate_to_datetime

from gmail_integration.application.dto import ImportableMessage

SYSTEM_LABEL_NAMES = {"INBOX": "Inbox", "UNREAD": "Unread", "IMPORTANT": "Important",
                      "STARRED": "Starred", "SENT": "Sent", "CATEGORY_PERSONAL": "Personal",
                      "CATEGORY_SOCIAL": "Social", "CATEGORY_PROMOTIONS": "Promotions",
                      "CATEGORY_UPDATES": "Updates", "CATEGORY_FORUMS": "Forums"}


def _b64(data: str | None, charset: str = "utf-8") -> str:
    if not data:
        return ""
    raw = base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))
    try:
        return raw.decode(charset or "utf-8", errors="replace")
    except LookupError:
        return raw.decode("utf-8", errors="replace")


def _charset(part: dict) -> str:
    for h in part.get("headers", []) or []:
        if h.get("name", "").lower() == "content-type" and "charset=" in h.get("value", "").lower():
            return h["value"].lower().split("charset=")[1].split(";")[0].strip().strip('"')
    return "utf-8"


def _walk(part: dict, out: dict) -> None:
    mime = (part.get("mimeType") or "").lower()
    body = part.get("body") or {}
    filename = part.get("filename") or ""
    if filename and (body.get("attachmentId") or body.get("size")):
        out["attachments"].append({"external_attachment_id": body.get("attachmentId", ""),
                                   "filename": filename, "mime_type": mime,
                                   "size": int(body.get("size") or 0)})
    elif mime == "text/plain" and not out["text"]:
        out["text"] = _b64(body.get("data"), _charset(part))
    elif mime == "text/html" and not out["html"]:
        out["html"] = _b64(body.get("data"), _charset(part))
    for child in part.get("parts", []) or []:
        _walk(child, out)


def parse_message(resource: dict) -> ImportableMessage:
    payload = resource.get("payload") or {}
    headers = {h["name"].lower(): h["value"] for h in payload.get("headers", []) if "name" in h}
    name, addr = parseaddr(headers.get("from", ""))
    recipients = []
    for kind in ("to", "cc"):
        for rname, raddr in getaddresses([headers.get(kind, "")]):
            if raddr:
                recipients.append({"type": kind, "email": raddr, "name": rname})
    out: dict = {"text": "", "html": "", "attachments": []}
    _walk(payload, out)
    if "internalDate" in resource:
        received = datetime.fromtimestamp(int(resource["internalDate"]) / 1000, tz=UTC)
    else:
        try:
            received = parsedate_to_datetime(headers.get("date", ""))
        except (TypeError, ValueError):
            received = datetime.now(UTC)
    label_ids = resource.get("labelIds") or []
    return ImportableMessage(
        external_message_id=resource["id"],
        external_thread_id=resource.get("threadId", ""),
        sender_name=name,
        sender_email=addr,
        recipients=recipients,
        subject=headers.get("subject", ""),
        body_text=out["text"],
        body_html=out["html"],
        snippet=resource.get("snippet", ""),
        received_at=received,
        is_read="UNREAD" not in label_ids,
        labels=[(lid, SYSTEM_LABEL_NAMES.get(lid, lid)) for lid in label_ids],
        attachments=out["attachments"],
        history_id=resource.get("historyId"),
    )
