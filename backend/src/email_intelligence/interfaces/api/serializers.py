from rest_framework import serializers


class ReanalyzeResponseSerializer(serializers.Serializer):
    analysis_id = serializers.IntegerField()
    status = serializers.CharField()
    model = serializers.CharField()
    prompt_version = serializers.CharField()


class BulkAnalyzeRequestSerializer(serializers.Serializer):
    force = serializers.BooleanField(required=False, default=False)


class BulkAnalyzeResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    provider = serializers.CharField()
    model = serializers.CharField()
    prompt_version = serializers.CharField()
    force = serializers.BooleanField()


class FailureModeSerializer(serializers.Serializer):
    mode = serializers.ChoiceField(choices=["none", "invalid_json", "bad_enum", "out_of_range", "timeout"])


class AttentionEmailSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    sender_name = serializers.CharField()
    sender_email = serializers.CharField()
    subject = serializers.CharField()
    snippet = serializers.CharField()
    received_at = serializers.DateTimeField()
    is_read = serializers.BooleanField()


class AttentionAnalysisSerializer(serializers.Serializer):
    priority = serializers.CharField()
    priority_confidence = serializers.IntegerField()
    reply_urgency = serializers.IntegerField()
    spam_likelihood = serializers.IntegerField()
    category = serializers.CharField()
    analyzed_at = serializers.DateTimeField(allow_null=True)


class AttentionItemSerializer(serializers.Serializer):
    email = AttentionEmailSerializer()
    analysis = AttentionAnalysisSerializer()
    reasons = serializers.ListField(child=serializers.CharField())


class NeedsAttentionSerializer(serializers.Serializer):
    description = serializers.CharField()
    ai_suggestion = serializers.BooleanField()
    thresholds = serializers.DictField()
    total = serializers.IntegerField()
    results = AttentionItemSerializer(many=True)
