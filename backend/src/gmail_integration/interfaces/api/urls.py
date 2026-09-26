from django.urls import path

from . import views

urlpatterns = [
    path("integrations/gmail", views.GmailConnectionView.as_view(), name="gmail-connection"),
    path("integrations/gmail/connect", views.GmailConnectView.as_view(), name="gmail-connect"),
    path("integrations/gmail/callback", views.GmailCallbackView.as_view(), name="gmail-callback"),
    path("integrations/gmail/fake-consent", views.FakeConsentView.as_view(), name="gmail-fake-consent"),
    path("integrations/gmail/<int:account_id>", views.GmailAccountDetailView.as_view(), name="gmail-account"),
    path("integrations/gmail/<int:account_id>/sync", views.GmailSyncView.as_view(), name="gmail-sync"),
    path("integrations/gmail/<int:account_id>/syncs", views.GmailSyncListView.as_view(), name="gmail-syncs"),
    path("demo/status", views.DemoStatusView.as_view(), name="demo-status"),
    path("demo/gmail/<int:account_id>/new-messages", views.DemoNewMessagesView.as_view(), name="demo-new-messages"),
    path("demo/gmail/<int:account_id>/revoke", views.DemoRevokeView.as_view(), name="demo-revoke"),
    path("demo/gmail/<int:account_id>/rate-limit", views.DemoRateLimitView.as_view(), name="demo-rate-limit"),
]
