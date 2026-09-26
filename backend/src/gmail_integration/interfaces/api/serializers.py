from rest_framework import serializers

# NOTE: no token fields exist on these serializers — OAuth credentials never leave the server.


class SyncSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    type = serializers.ChoiceField(choices=["INITIAL", "INCREMENTAL"])
    status = serializers.ChoiceField(choices=["PENDING", "RUNNING", "COMPLETED", "PARTIAL", "FAILED"])
    fetched_count = serializers.IntegerField()
    imported_count = serializers.IntegerField()
    failed_count = serializers.IntegerField()
    started_at = serializers.DateTimeField(allow_null=True)
    completed_at = serializers.DateTimeField(allow_null=True)
    error = serializers.CharField(allow_blank=True)
    created_at = serializers.DateTimeField()


class GmailAccountSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    email = serializers.EmailField()
    status = serializers.ChoiceField(choices=["ACTIVE", "REVOKED", "ERROR", "DISCONNECTED"])
    last_synced_at = serializers.DateTimeField(allow_null=True)
    next_sync_at = serializers.DateTimeField(allow_null=True)
    last_error = serializers.CharField(allow_blank=True)
    created_at = serializers.DateTimeField()
    latest_sync = SyncSerializer(allow_null=True)
    sync_in_progress = serializers.SerializerMethodField()

    def get_sync_in_progress(self, obj) -> bool:
        return bool(obj.latest_sync and obj.latest_sync.status in ("PENDING", "RUNNING"))


class GmailConnectionSerializer(serializers.Serializer):
    connected = serializers.BooleanField()
    account = GmailAccountSerializer(allow_null=True)
    demo_mode = serializers.BooleanField()


class DemoStatusSerializer(serializers.Serializer):
    demo_mode = serializers.BooleanField()
    gmail_gateway = serializers.CharField()
    ai_provider = serializers.CharField()
