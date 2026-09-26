from django.urls import path

from . import views

urlpatterns = [
    path("emails", views.InboxView.as_view(), name="emails"),
    path("emails/<int:email_id>", views.EmailDetailView.as_view(), name="email-detail"),
    path("dashboard/summary", views.DashboardSummaryView.as_view(), name="dashboard-summary"),
    path("threads/<str:thread_id>", views.ThreadView.as_view(), name="thread"),
]
