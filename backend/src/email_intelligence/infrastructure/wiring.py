"""Composition root for Email Intelligence: EmailImported → analysis."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def _on_email_imported(event) -> None:
    from email_intelligence.infrastructure import container
    from shared_kernel.domain import NotFoundError

    try:
        container.request_analysis()(email_id=event.email_id)
    except NotFoundError:
        logger.warning("imported email vanished before analysis", extra={"email_id": event.email_id})


def _on_analysis_finished(event) -> None:
    logger.info("email analysis finished",
                extra={"analysis_id": event.analysis_id, "event": event.name})


def register() -> None:
    from email_intelligence.domain.events import EmailAnalysisCompleted, EmailAnalysisFailed
    from mailbox_context.application.facade import EmailImported
    from shared_kernel.infrastructure.event_bus import event_bus

    event_bus.subscribe(EmailImported, _on_email_imported)
    event_bus.subscribe(EmailAnalysisCompleted, _on_analysis_finished)
    event_bus.subscribe(EmailAnalysisFailed, _on_analysis_finished)
