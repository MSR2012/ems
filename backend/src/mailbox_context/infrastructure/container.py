from mailbox_context.application.queries.dashboard import GetDashboardSummary
from mailbox_context.application.queries.inbox import GetEmailDetail, GetThread, ListInbox

from .persistence.queries import DjangoDashboardQueryService, DjangoInboxQueryService


def list_inbox() -> ListInbox:
    return ListInbox(DjangoInboxQueryService())


def email_detail() -> GetEmailDetail:
    return GetEmailDetail(DjangoInboxQueryService())


def thread() -> GetThread:
    return GetThread(DjangoInboxQueryService())


def dashboard_summary() -> GetDashboardSummary:
    return GetDashboardSummary(DjangoDashboardQueryService())
