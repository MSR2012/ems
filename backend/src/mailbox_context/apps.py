from django.apps import AppConfig


class MailboxConfig(AppConfig):
    name = "mailbox_context"
    label = "mailbox"
    verbose_name = "Mailbox"

    def ready(self) -> None:
        from mailbox_context.infrastructure import wiring

        wiring.register()
