"""Error tracking hooks + Celery task failure visibility (no task args, which may hold content)."""

from __future__ import annotations

import logging

from django.conf import settings

logger = logging.getLogger("tasks")


def init_sentry() -> None:
    if not settings.SENTRY_DSN:
        return
    try:
        import sentry_sdk
    except ImportError:  # optional dependency
        logger.warning("SENTRY_DSN set but sentry-sdk is not installed")
        return

    def before_send(event, hint):
        # Drop request bodies / local variables that could contain email content or tokens.
        event.get("request", {}).pop("data", None)
        for exc in (event.get("exception") or {}).get("values", []):
            for frame in (exc.get("stacktrace") or {}).get("frames", []):
                frame.pop("vars", None)
        return event

    sentry_sdk.init(dsn=settings.SENTRY_DSN, send_default_pii=False, before_send=before_send,
                    traces_sample_rate=0.0)


def connect_celery_signals() -> None:
    from celery.signals import task_failure, task_retry

    @task_failure.connect(weak=False)
    def _on_failure(sender=None, task_id=None, exception=None, **_):
        logger.error("celery task failed", extra={"task": getattr(sender, "name", str(sender)),
                                                  "task_id": task_id,
                                                  "error_type": type(exception).__name__})

    @task_retry.connect(weak=False)
    def _on_retry(sender=None, request=None, reason=None, **_):
        logger.warning("celery task retry", extra={"task": getattr(sender, "name", str(sender)),
                                                   "task_id": getattr(request, "id", None),
                                                   "reason_type": type(reason).__name__})
