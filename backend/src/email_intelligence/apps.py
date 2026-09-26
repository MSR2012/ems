from django.apps import AppConfig


class EmailIntelligenceConfig(AppConfig):
    name = "email_intelligence"
    label = "email_intelligence"
    verbose_name = "Email Intelligence"

    def ready(self) -> None:
        from email_intelligence.infrastructure import wiring

        wiring.register()
