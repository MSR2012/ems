"""Celery app: queues sync/analysis/default, routing by task-name prefix, Beat schedule."""

import os

from celery import Celery
from kombu import Queue

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("emp")
app.config_from_object("django.conf:settings", namespace="CELERY")

app.conf.task_queues = (Queue("sync"), Queue("analysis"), Queue("default"))
app.conf.task_default_queue = "default"
# Route by task-name prefix so AI backlog can never starve synchronization (§22).
app.conf.task_routes = {
    "gmail_integration.*": {"queue": "sync"},
    "email_intelligence.*": {"queue": "analysis"},
    "mailbox.*": {"queue": "default"},
}


# Beat: enqueue due Gmail syncs every SYNC_DISPATCH_INTERVAL seconds (§23).
app.conf.beat_schedule = {
    "gmail-dispatch-due-syncs": {
        "task": "gmail_integration.dispatch_due_syncs",
        "schedule": float(os.environ.get("SYNC_DISPATCH_INTERVAL", "60")),
    },
    "ai-requeue-stale-analyses": {
        "task": "email_intelligence.requeue_stale_analyses",
        "schedule": 60.0,
    },
}

# Each context keeps its Celery tasks in <context>.infrastructure.tasks
app.autodiscover_tasks(
    [
        "gmail_integration.infrastructure",
        "mailbox_context.infrastructure",
        "email_intelligence.infrastructure",
    ],
    related_name="tasks",
)
