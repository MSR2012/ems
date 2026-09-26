from django.conf import settings
from django.db import models
from django.db.models import Q


class GmailAccountModel(models.Model):
    STATUS_CHOICES = [(s, s) for s in ("ACTIVE", "REVOKED", "ERROR", "DISCONNECTED")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="gmail_accounts")
    google_account_id = models.CharField(max_length=255)
    email = models.EmailField()
    # Ciphertext only (TokenCipher / Fernet). Never serialized.
    encrypted_access_token = models.TextField(blank=True, default="")
    encrypted_refresh_token = models.TextField(blank=True, default="")
    token_expires_at = models.DateTimeField(null=True, blank=True)
    scopes = models.JSONField(default=list, blank=True)
    history_id = models.CharField(max_length=64, blank=True, default="")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="ACTIVE")
    last_error = models.CharField(max_length=500, blank=True, default="")
    last_synced_at = models.DateTimeField(null=True, blank=True)
    next_sync_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "gmail_accounts"
        app_label = "gmail_integration"
        constraints = [
            models.UniqueConstraint(fields=["user", "google_account_id"],
                                    name="uniq_gmail_account_per_user"),
        ]
        indexes = [
            models.Index(fields=["status", "next_sync_at"], name="gmail_acc_due_idx"),
        ]


class EmailSyncModel(models.Model):
    TYPE_CHOICES = [("INITIAL", "INITIAL"), ("INCREMENTAL", "INCREMENTAL")]
    STATUS_CHOICES = [(s, s) for s in ("PENDING", "RUNNING", "COMPLETED", "PARTIAL", "FAILED")]

    gmail_account = models.ForeignKey(GmailAccountModel, on_delete=models.CASCADE,
                                      related_name="syncs")
    type = models.CharField(max_length=16, choices=TYPE_CHOICES)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="PENDING")
    fetched_count = models.PositiveIntegerField(default=0)
    imported_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "email_syncs"
        app_label = "gmail_integration"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["gmail_account", "-created_at"], name="email_sync_acc_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(status__in=["PENDING", "RUNNING", "COMPLETED", "PARTIAL", "FAILED"]),
                name="email_sync_status_valid",
            ),
        ]


class FakeMailboxModel(models.Model):
    """State of the demo-mode fake Gmail mailbox (shared by api and worker processes)."""

    google_account_id = models.CharField(max_length=255, unique=True)
    email = models.EmailField()
    anchor_at = models.DateTimeField()  # base messages are dated relative to this
    batch_times = models.JSONField(default=list, blank=True)  # ISO delivery time per new-mail batch
    revoked = models.BooleanField(default=False)
    rate_limit_failures = models.PositiveIntegerField(default=0)  # next N API calls → 429
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "fake_gmail_mailboxes"
        app_label = "gmail_integration"
