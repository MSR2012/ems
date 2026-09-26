from django.core.management.base import BaseCommand

from email_intelligence.infrastructure import container


class Command(BaseCommand):
    help = ("Queue re-analysis for emails that have no analysis for the active AI model / "
            "AI_PROMPT_VERSION (run after changing either).")

    def add_arguments(self, parser):
        parser.add_argument("--user-id", type=int, default=None,
                            help="Only this user's emails (all of them, not just previously analyzed)")
        parser.add_argument("--force", action="store_true",
                            help="Also re-run analyses that already completed with this version")

    def handle(self, *args, user_id=None, force=False, **options):
        v = container.version()
        n = container.reanalyze_emails()(user_id=user_id, force=force)
        self.stdout.write(self.style.SUCCESS(
            f"Queued {n} analyses for model={v.model} prompt_version={v.prompt_version}"))
