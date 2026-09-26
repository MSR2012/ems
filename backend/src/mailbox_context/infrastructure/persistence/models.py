from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import models


class EmailModel(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="emails")
    # Provider-neutral account reference (ID only; no FK across bounded contexts).
    mail_account_id = models.BigIntegerField()
    provider = models.CharField(max_length=32, default="gmail")
    external_message_id = models.CharField(max_length=255)
    external_thread_id = models.CharField(max_length=255, blank=True, default="")
    sender_name = models.CharField(max_length=255, blank=True, default="")
    sender_email = models.CharField(max_length=320)
    recipients = models.JSONField(default=list, blank=True)
    subject = models.TextField(blank=True, default="")
    body_text = models.TextField(blank=True, default="")
    body_html_sanitized = models.TextField(blank=True, default="")
    snippet = models.CharField(max_length=255, blank=True, default="")
    received_at = models.DateTimeField()
    is_read = models.BooleanField(default=False)
    # Maintained by a PostgreSQL trigger (see migration) — sender, subject, body.
    search_vector = SearchVectorField(null=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "emails"
        app_label = "mailbox"
        constraints = [
            models.UniqueConstraint(fields=["mail_account_id", "external_message_id"],
                                    name="uniq_email_per_account_message"),
        ]
        indexes = [
            models.Index(fields=["user", "-received_at"], name="emails_user_received_idx"),
            models.Index(fields=["user", "is_read"], name="emails_user_read_idx"),
            models.Index(fields=["external_thread_id"], name="emails_thread_idx"),
            GinIndex(fields=["search_vector"], name="emails_search_gin"),
        ]


class EmailLabelModel(models.Model):
    email = models.ForeignKey(EmailModel, on_delete=models.CASCADE, related_name="labels")
    external_label_id = models.CharField(max_length=255)
    name = models.CharField(max_length=255)

    class Meta:
        db_table = "email_labels"
        app_label = "mailbox"
        constraints = [
            models.UniqueConstraint(fields=["email", "external_label_id"],
                                    name="uniq_label_per_email"),
        ]


class EmailAttachmentModel(models.Model):
    email = models.ForeignKey(EmailModel, on_delete=models.CASCADE, related_name="attachments")
    external_attachment_id = models.CharField(max_length=512, blank=True, default="")
    filename = models.CharField(max_length=512)
    mime_type = models.CharField(max_length=255, blank=True, default="")
    size = models.BigIntegerField(default=0)

    class Meta:
        db_table = "email_attachments"
        app_label = "mailbox"


class CurrentAnalysisReadModel(models.Model):
    """Read-only projection over the `current_email_analyses` view published by the Email
    Intelligence context (its migration owns the view). Mailbox never imports that
    context's code; the database view is the published read-model contract."""

    email = models.OneToOneField(EmailModel, primary_key=True, on_delete=models.DO_NOTHING,
                                 db_constraint=False, related_name="current_analysis")
    analysis_id = models.BigIntegerField()
    status = models.CharField(max_length=16)
    priority = models.CharField(max_length=16, null=True)
    priority_confidence = models.SmallIntegerField(null=True)
    spam_likelihood = models.SmallIntegerField(null=True)
    reply_urgency = models.SmallIntegerField(null=True)
    category = models.CharField(max_length=32, null=True)
    sentiment = models.CharField(max_length=16, null=True)
    model = models.CharField(max_length=128)
    model_version = models.CharField(max_length=128, null=True)
    prompt_version = models.CharField(max_length=64)
    analyzed_at = models.DateTimeField(null=True)
    error = models.TextField(null=True)
    latest_status = models.CharField(max_length=16, null=True)  # newest row (e.g. re-analysis)

    class Meta:
        managed = False
        db_table = "current_email_analyses"
        app_label = "mailbox"
