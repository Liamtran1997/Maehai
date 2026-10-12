import uuid
from pathlib import Path

from django.db import models
from django.db.models import Q

from maehai.core.storage import private_storage
from maehai.orders.models import Order


def slip_path(instance, filename: str) -> str:
    """slips/<year>/<month>/<random>.<ext>. Unguessable name: slips show bank details, so never keep the customer's filename."""
    from django.utils import timezone

    now = timezone.now()
    return f"slips/{now:%Y}/{now:%m}/{uuid.uuid4().hex}{Path(filename).suffix.lower()[:5]}"


class PaymentStatus(models.TextChoices):
    PENDING = "pending", "รอชำระ"
    SLIP_SUBMITTED = "slip_submitted", "รอตรวจสลิป"
    CONFIRMED = "confirmed", "ยืนยันแล้ว"
    REJECTED = "rejected", "ไม่ผ่าน"
    EXPIRED = "expired", "หมดอายุ"


class Payment(models.Model):
    """One PromptPay attempt for an order. Amount is fixed when the QR is made."""

    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="payments")
    method = models.CharField(max_length=20, default="promptpay")
    amount_satang = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)
    qr_payload = models.TextField(blank=True)
    expires_at = models.DateTimeField()
    slip = models.ImageField(upload_to=slip_path, blank=True, storage=private_storage)  # never public, either backend
    slip_submitted_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.CharField(max_length=80, blank=True)
    reject_reason = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]
        constraints = [
            models.CheckConstraint(condition=Q(amount_satang__gt=0), name="payment_amount_positive"),
            # At most one confirmed payment per order: a paid order can never be paid twice.
            models.UniqueConstraint(fields=["order"], condition=Q(status="confirmed"), name="one_confirmed_payment_per_order"),
        ]
