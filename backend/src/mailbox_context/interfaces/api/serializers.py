from datetime import datetime, time

from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

PRIORITIES = ["CRITICAL", "HIGH", "NORMAL", "LOW"]
CATEGORIES = ["WORK", "PERSONAL", "FINANCE", "CUSTOMER", "SALES", "MARKETING", "SOCIAL",
              "NOTIFICATION", "TRANSACTION", "SUPPORT", "NEWSLETTER", "OTHER"]
ANALYSIS_STATUS = ["PENDING", "RUNNING", "COMPLETED", "FAILED", "SKIPPED"]


@extend_schema_field(OpenApiTypes.STR)
class CsvChoiceField(serializers.Field):
    """Comma-separated list of enum values, e.g. `priority=CRITICAL,HIGH`."""

    def __init__(self, choices, **kwargs):
        self.choices = choices
        super().__init__(**kwargs)

    def to_internal_value(self, data):
        values = [v.strip().upper() for v in str(data).split(",") if v.strip()]
        bad = [v for v in values if v not in self.choices]
        if bad:
            raise serializers.ValidationError(f"Invalid value(s): {', '.join(bad)}. "
                                              f"Allowed: {', '.join(self.choices)}.")
        return tuple(dict.fromkeys(values))


@extend_schema_field(OpenApiTypes.STR)
class FlexibleDateTimeField(serializers.Field):
    """Accepts YYYY-MM-DD (start/end of day) or a full ISO datetime."""

    def __init__(self, end_of_day=False, **kwargs):
        self.end_of_day = end_of_day
        super().__init__(**kwargs)

    def to_internal_value(self, data):
        s = str(data).strip()
        try:
            if len(s) == 10:
                d = datetime.strptime(s, "%Y-%m-%d").date()
                dt = datetime.combine(d, time.max if self.end_of_day else time.min)
                return timezone.make_aware(dt, timezone.get_current_timezone())
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            return dt if timezone.is_aware(dt) else timezone.make_aware(dt)
        except ValueError as exc:
            raise serializers.ValidationError("Use YYYY-MM-DD or an ISO 8601 datetime.") from exc


class InboxQuerySerializer(serializers.Serializer):
    q = serializers.CharField(required=False, allow_blank=True, max_length=200, default="")
    priority = CsvChoiceField(PRIORITIES, required=False)
    category = CsvChoiceField(CATEGORIES, required=False)
    spam_likelihood_min = serializers.IntegerField(required=False, min_value=0, max_value=100)
    spam_likelihood_max = serializers.IntegerField(required=False, min_value=0, max_value=100)
    reply_urgency_min = serializers.IntegerField(required=False, min_value=0, max_value=100)
    reply_urgency_max = serializers.IntegerField(required=False, min_value=0, max_value=100)
    hide_potential_spam = serializers.BooleanField(required=False, default=False)
    is_read = serializers.BooleanField(required=False, allow_null=True, default=None)
    received_from = FlexibleDateTimeField(required=False)
    received_to = FlexibleDateTimeField(required=False, end_of_day=True)
    page = serializers.IntegerField(required=False, min_value=1, default=1)
    page_size = serializers.IntegerField(required=False, min_value=1, max_value=100, default=25)

    def validate(self, attrs):
        for lo, hi in (("spam_likelihood_min", "spam_likelihood_max"),
                       ("reply_urgency_min", "reply_urgency_max"), ("received_from", "received_to")):
            if attrs.get(lo) is not None and attrs.get(hi) is not None and attrs[lo] > attrs[hi]:
                raise serializers.ValidationError({hi: [f"Must be greater than or equal to {lo}."]})
        return attrs


class AnalysisSummarySerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=ANALYSIS_STATUS)
    latest_status = serializers.ChoiceField(choices=ANALYSIS_STATUS)
    priority = serializers.ChoiceField(choices=PRIORITIES, allow_null=True)
    priority_confidence = serializers.IntegerField(allow_null=True)
    spam_likelihood = serializers.IntegerField(allow_null=True)
    reply_urgency = serializers.IntegerField(allow_null=True)
    category = serializers.ChoiceField(choices=CATEGORIES, allow_null=True)
    sentiment = serializers.CharField(allow_null=True)
    model = serializers.CharField()
    model_version = serializers.CharField(allow_null=True)
    prompt_version = serializers.CharField()
    analyzed_at = serializers.DateTimeField(allow_null=True)
    error = serializers.CharField(allow_null=True)
    is_potential_spam = serializers.BooleanField()
    is_high_urgency = serializers.BooleanField()


class InboxItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    thread_id = serializers.CharField()
    sender_name = serializers.CharField()
    sender_email = serializers.CharField()
    subject = serializers.CharField()
    snippet = serializers.CharField()
    received_at = serializers.DateTimeField()
    is_read = serializers.BooleanField()
    has_attachments = serializers.BooleanField()
    thread_count = serializers.IntegerField()
    analysis = AnalysisSummarySerializer(allow_null=True)


class InboxPageSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    page = serializers.IntegerField()
    page_size = serializers.IntegerField()
    next = serializers.IntegerField(allow_null=True)
    previous = serializers.IntegerField(allow_null=True)
    thresholds = serializers.DictField()
    results = InboxItemSerializer(many=True)


class AttachmentSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    filename = serializers.CharField()
    mime_type = serializers.CharField()
    size = serializers.IntegerField()


class ThreadMessageSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    sender_name = serializers.CharField()
    sender_email = serializers.CharField()
    subject = serializers.CharField()
    snippet = serializers.CharField()
    received_at = serializers.DateTimeField()
    is_read = serializers.BooleanField()


class RecipientSerializer(serializers.Serializer):
    type = serializers.CharField()
    email = serializers.CharField()
    name = serializers.CharField(allow_blank=True)


class EmailDetailSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    provider = serializers.CharField()
    external_message_id = serializers.CharField()
    thread_id = serializers.CharField()
    sender_name = serializers.CharField()
    sender_email = serializers.CharField()
    recipients = RecipientSerializer(many=True)
    subject = serializers.CharField()
    body_text = serializers.CharField()
    body_html_sanitized = serializers.CharField()
    snippet = serializers.CharField()
    received_at = serializers.DateTimeField()
    is_read = serializers.BooleanField()
    labels = serializers.ListField(child=serializers.CharField())
    attachments = AttachmentSerializer(many=True)
    analysis = AnalysisSummarySerializer(allow_null=True)
    thread = ThreadMessageSerializer(many=True)


class ThreadSerializer(serializers.Serializer):
    thread_id = serializers.CharField()
    subject = serializers.CharField()
    messages = EmailDetailSerializer(many=True)


class DashboardCountsSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    unread = serializers.IntegerField()
    high_priority = serializers.IntegerField()
    high_urgency = serializers.IntegerField()
    potential_spam = serializers.IntegerField()


class AnalysisProgressSerializer(serializers.Serializer):
    analyzed = serializers.IntegerField()
    in_progress = serializers.IntegerField()
    failed = serializers.IntegerField()
    skipped = serializers.IntegerField()


class DashboardSyncSerializer(serializers.Serializer):
    provider = serializers.CharField()
    connected = serializers.BooleanField()
    status = serializers.CharField()
    email = serializers.CharField(allow_null=True)
    last_synced_at = serializers.DateTimeField(allow_null=True)
    latest_sync = serializers.DictField(allow_null=True)


class DashboardSummarySerializer(serializers.Serializer):
    counts = DashboardCountsSerializer()
    analysis = AnalysisProgressSerializer()
    recent = InboxItemSerializer(many=True)
    sync = DashboardSyncSerializer(allow_null=True)
    thresholds = serializers.DictField()
