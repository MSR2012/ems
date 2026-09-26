from django.apps import AppConfig


class SharedKernelConfig(AppConfig):
    name = "shared_kernel"
    label = "shared_kernel"
    verbose_name = "Shared kernel"

    def ready(self) -> None:
        from .infrastructure.observability import connect_celery_signals, init_sentry

        init_sentry()
        connect_celery_signals()
