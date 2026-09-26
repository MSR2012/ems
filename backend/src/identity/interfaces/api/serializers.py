from rest_framework import serializers


class RegisterSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)


class PasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, trim_whitespace=False)


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True, trim_whitespace=False)
    new_password = serializers.CharField(write_only=True, trim_whitespace=False)


class AppSettingsSerializer(serializers.Serializer):
    spam_threshold_percent = serializers.IntegerField()
    urgency_threshold_percent = serializers.IntegerField()
    ai_provider = serializers.CharField()
    ai_provider_name = serializers.CharField()
    demo_mode = serializers.BooleanField()


class MeSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    email = serializers.EmailField(read_only=True)
    name = serializers.CharField(max_length=150, allow_blank=True)
    created_at = serializers.DateTimeField(read_only=True)
    settings = AppSettingsSerializer(read_only=True)


class SessionSerializer(serializers.Serializer):
    authenticated = serializers.BooleanField()
    user = MeSerializer(allow_null=True)


class MessageSerializer(serializers.Serializer):
    detail = serializers.CharField()
