from django.urls import path

from . import views

urlpatterns = [
    path("emails/analyze", views.BulkAnalyzeView.as_view(), name="emails-bulk-analyze"),
    path("emails/<int:email_id>/reanalyze", views.ReanalyzeView.as_view(), name="email-reanalyze"),
    path("dashboard/needs-attention", views.NeedsAttentionView.as_view(), name="needs-attention"),
    path("demo/ai/failure-mode", views.DemoAiFailureModeView.as_view(), name="demo-ai-failure-mode"),
]
