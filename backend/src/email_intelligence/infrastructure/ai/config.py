from django.conf import settings

FAKE_PROVIDER = "fake"
FAKE_MODEL = "fake-classifier-1"


def active_provider() -> str:
    return settings.AI_PROVIDER


def active_model() -> str:
    if settings.AI_PROVIDER == "openrouter":
        return settings.OPENROUTER_MODEL
    return FAKE_MODEL if settings.AI_PROVIDER == FAKE_PROVIDER else settings.JEV_AI_MODEL


def active_prompt_version() -> str:
    return settings.AI_PROMPT_VERSION
