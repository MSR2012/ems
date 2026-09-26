from django.conf import settings
from django.db import models
from django.db.models import Q

_PCT = ("priority_confidence", "spam_likelihood", "reply_urgency")


class EmailAnalysisModel(models.Model):
    STATUS = [(s, s) for s in ("PENDING", "RUNNING", "COMPLETED", "FAILED", "SKIPPED")]
    PRIORITY = [(s, s) for s in ("CRITICAL", "HIGH", "NORMAL", "LOW")]
    CATEGORY = [(s, s) for s in ("WORK", "PERSONAL", "FINANCE", "CUSTOMER", "SALES", "MARKETING",
                                 "SOCIAL", "NOTIFICATION", "TRANSACTION", "SUPPORT",
                                 "NEWSLETTER", "OTHER")]
    SENTIMENT = [(s, s) for s in ("POSITIVE", "NEUTRAL", "NEGATIVE")]

    # Cross-context reference by ID only (emails belong to the Mailbox context).
    email_id = models.BigIntegerField()
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="email_analyses")
    status = models.CharField(max_length=16, choices=STATUS, default="PENDING")
    priority = models.CharField(max_length=16, choices=PRIORITY, null=True, blank=True)
    priority_confidence = models.SmallIntegerField(null=True, blank=True)
    spam_likelihood = models.SmallIntegerField(null=True, blank=True)
    reply_urgency = models.SmallIntegerField(null=True, blank=True)
    category = models.CharField(max_length=32, choices=CATEGORY, null=True, blank=True)
    sentiment = models.CharField(max_length=16, choices=SENTIMENT, null=True, blank=True)
    model = models.CharField(max_length=128)
    # Concrete version the provider reports (e.g. "jev-1.13.0" for model "jev-latest").
    model_version = models.CharField(max_length=128, null=True, blank=True)
    prompt_version = models.CharField(max_length=64)
    analyzed_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True, default="")
    attempts = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "email_analyses"
        app_label = "email_intelligence"
        constraints = [
            models.UniqueConstraint(fields=["email_id", "prompt_version", "model"],
                                    name="uniq_analysis_per_email_version"),
            *[models.CheckConstraint(condition=Q(**{f"{f}__gte": 0}) & Q(**{f"{f}__lte": 100}),
                                     name=f"email_analysis_{f}_0_100") for f in _PCT],
            models.CheckConstraint(
                condition=~Q(status="COMPLETED") | (
                    Q(priority__isnull=False) & Q(category__isnull=False)
                    & Q(spam_likelihood__isnull=False) & Q(reply_urgency__isnull=False)
                    & Q(analyzed_at__isnull=False)),
                name="email_analysis_completed_has_result",
            ),
        ]
        indexes = [
            models.Index(fields=["email_id", "-analyzed_at"], name="analysis_email_idx"),
            models.Index(fields=["user", "priority"], name="analysis_user_priority_idx"),
            models.Index(fields=["user", "reply_urgency"], name="analysis_user_urgency_idx"),
            models.Index(fields=["user", "category"], name="analysis_user_category_idx"),
            models.Index(fields=["user", "spam_likelihood"], name="analysis_user_spam_idx"),
            models.Index(fields=["user", "status"], name="analysis_user_status_idx"),
        ]


class AiUsageLogModel(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="ai_usage_logs")
    email_id = models.BigIntegerField()
    provider = models.CharField(max_length=64)
    model = models.CharField(max_length=128)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    duration_ms = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=32)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ai_usage_logs"
        app_label = "email_intelligence"
        indexes = [models.Index(fields=["user", "-created_at"], name="ai_usage_user_idx")]
