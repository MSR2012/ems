from django.apps import AppConfig


class DemoConfig(AppConfig):
    """Development tooling (demo seed). Not a bounded context: it composes all of them."""

    name = "demo"
    label = "demo"
