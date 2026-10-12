from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.module_loading import import_string

from .line import LineError
from .models import Outbox


def configured() -> bool:
    return bool(settings.LINE_CHANNEL_ACCESS_TOKEN)


def deliver_pending(limit: int = 50, now=None) -> dict:
    """Send due messages. Safe to run from several workers: rows are claimed with SKIP LOCKED where the database supports it."""
    now = now or timezone.now()
    counts = {"sent": 0, "failed": 0, "retry": 0, "skipped": 0}
    client = import_string(settings.LINE_CLIENT)() if configured() else None

    with transaction.atomic():
        rows = list(Outbox.objects.select_for_update(skip_locked=True)
                    .filter(status=Outbox.Status.PENDING, send_after__lte=now).order_by("id")[:limit])
        for row in rows:
            if client is None:
                row.status, row.last_error = Outbox.Status.SKIPPED, "LINE is not configured"
                counts["skipped"] += 1
                row.save(update_fields=["status", "last_error"])
                continue
            row.attempts += 1
            try:
                client.push(row.recipient, row.text, str(row.retry_key))
            except LineError as e:
                row.last_error = str(e)[:300]
                if e.retryable and row.attempts < settings.NOTIFY_MAX_ATTEMPTS:
                    row.send_after = now + timedelta(minutes=2 ** row.attempts)  # 2, 4, 8, 16 minutes
                    counts["retry"] += 1
                else:
                    row.status = Outbox.Status.FAILED
                    counts["failed"] += 1
            else:
                row.status, row.sent_at, row.last_error = Outbox.Status.SENT, now, ""
                counts["sent"] += 1
            row.save(update_fields=["status", "attempts", "last_error", "send_after", "sent_at"])
    return counts
