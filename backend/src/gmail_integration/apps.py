from django.apps import AppConfig


class GmailIntegrationConfig(AppConfig):
    name = "gmail_integration"
    label = "gmail_integration"
    verbose_name = "Gmail Integration"

    def ready(self) -> None:
        from gmail_integration.infrastructure import wiring

        wiring.register()
