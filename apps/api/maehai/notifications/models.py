import uuid

from django.db import models
from django.utils import timezone


class Outbox(models.Model):
    """Messages waiting to be pushed to LINE. Rows are written in the same transaction as the change they report,
    so an order never changes without its notification being queued, and a LINE outage never blocks an order."""

    class Status(models.TextChoices):
        PENDING = "pending", "รอส่ง"
        SENT = "sent", "ส่งแล้ว"
        FAILED = "failed", "ส่งไม่สำเร็จ"
        SKIPPED = "skipped", "ข้าม (ยังไม่ตั้งค่า LINE)"

    audience = models.CharField(max_length=10, choices=[("customer", "customer"), ("staff", "staff")])
    recipient = models.CharField(max_length=64, help_text="LINE user or group ID")
    kind = models.CharField(max_length=40)
    text = models.TextField()
    order = models.ForeignKey("orders.Order", on_delete=models.CASCADE, null=True, blank=True, related_name="notifications")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    last_error = models.CharField(max_length=300, blank=True)
    retry_key = models.UUIDField(default=uuid.uuid4, editable=False, help_text="Sent as X-Line-Retry-Key so LINE drops duplicates on retry")
    send_after = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["id"]
        indexes = [models.Index(fields=["status", "send_after"])]
