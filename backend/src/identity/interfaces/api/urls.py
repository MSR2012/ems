from django.urls import path

from . import views

urlpatterns = [
    path("auth/csrf", views.CsrfView.as_view(), name="auth-csrf"),
    path("auth/session", views.SessionView.as_view(), name="auth-session"),
    path("auth/register", views.RegisterView.as_view(), name="auth-register"),
    path("auth/login", views.LoginView.as_view(), name="auth-login"),
    path("auth/logout", views.LogoutView.as_view(), name="auth-logout"),
    path("auth/password-reset", views.PasswordResetView.as_view(), name="auth-password-reset"),
    path("auth/password-reset/confirm", views.PasswordResetConfirmView.as_view(),
         name="auth-password-reset-confirm"),
    path("me", views.MeView.as_view(), name="me"),
    path("me/password", views.ChangePasswordView.as_view(), name="me-password"),
]
