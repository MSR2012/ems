"""Composition root for the Gmail Integration context: event subscriptions & providers."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class GmailSyncStatusProvider:
    """Feeds the Mailbox dashboard with connection/sync status (published via the facade)."""

    def status_for_user(self, user_id: int) -> dict | None:
        from gmail_integration.infrastructure import container

        views = container.get_connection()(user_id=user_id)
        active = [v for v in views if v.status != "DISCONNECTED"]
        if not active:
            return {"provider": "gmail", "connected": False, "status": "DISCONNECTED",
                    "email": None, "last_synced_at": None, "latest_sync": None}
        v = active[0]
        latest = v.latest_sync
        return {
            "provider": "gmail", "connected": v.status in ("ACTIVE", "ERROR"), "status": v.status,
            "email": v.email, "last_synced_at": v.last_synced_at,
            "latest_sync": None if latest is None else {
                "id": latest.id, "type": latest.type, "status": latest.status,
                "imported_count": latest.imported_count, "started_at": latest.started_at,
                "completed_at": latest.completed_at, "error": latest.error,
            },
        }


def _on_connected(event) -> None:
    from django.conf import settings

    from gmail_integration.application.use_cases import SyncAlreadyRunning, SyncNotAllowed
    from gmail_integration.infrastructure import container

    try:
        # Small start delay lets the OAuth redirect land first so the UI shows the queued sync.
        container.request_sync()(account_id=event.account_id,
                                 delay_seconds=settings.INITIAL_SYNC_START_DELAY_SECONDS)
    except (SyncAlreadyRunning, SyncNotAllowed) as exc:
        logger.info("initial sync not requested: %s", exc)


def _on_revoked(event) -> None:
    logger.warning("gmail authorization revoked; scheduled syncs stopped",
                   extra={"account_id": event.account_id})


def _on_sync_finished(event) -> None:
    logger.info("gmail sync finished", extra={"sync_id": event.sync_id,
                                              "account_id": event.account_id,
                                              "event": event.name})


def register() -> None:
    from gmail_integration.domain.events import (
        EmailSyncCompleted,
        EmailSyncFailed,
        GmailAccountConnected,
        GmailAuthorizationRevoked,
    )
    from mailbox_context.application import facade
    from shared_kernel.infrastructure.event_bus import event_bus

    event_bus.subscribe(GmailAccountConnected, _on_connected)
    event_bus.subscribe(GmailAuthorizationRevoked, _on_revoked)
    event_bus.subscribe(EmailSyncCompleted, _on_sync_finished)
    event_bus.subscribe(EmailSyncFailed, _on_sync_finished)
    facade.register_sync_status_provider(GmailSyncStatusProvider())
