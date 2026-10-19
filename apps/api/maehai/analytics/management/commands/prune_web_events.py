from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from maehai.analytics.models import WebEvent


class Command(BaseCommand):
    help = "Deletes raw usage events older than WEB_EVENT_RETENTION_DAYS (180). Safe to repeat."

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=settings.WEB_EVENT_RETENTION_DAYS)
        deleted, _ = WebEvent.objects.filter(created_at__lt=cutoff).delete()
        self.stdout.write(self.style.SUCCESS(f"usage events deleted: {deleted}"))
