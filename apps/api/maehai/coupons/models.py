import re

from django.db import models
from django.db.models import F, Q
from django.utils import timezone

CODE_RE = re.compile(r"^[A-Z0-9][A-Z0-9-]{1,23}$")


class Coupon(models.Model):
    """A code a customer types at checkout for a discount on the whole order's goods (never on shipping).

    Rules (see docs/specs/coupons.md):
      - Applied to the goods total AFTER per-product promotions, so the two can be used together.
      - Percent coupons round half up to the satang and may have a cap. Amount coupons are satang off the order.
      - The discount can never push the goods total below 1 baht (PromptPay cannot charge 0).
      - Usage is counted per redemption. A cancelled order gives its use back.
    """

    class Kind(models.TextChoices):
        PERCENT = "percent", "ลดเป็นเปอร์เซ็นต์"
        AMOUNT = "amount", "ลดเป็นจำนวนเงิน"
        FREE_SHIPPING = "free_shipping", "ส่งฟรี (ยกเว้นค่าจัดส่ง)"

    code = models.CharField(max_length=24, unique=True, help_text="Stored upper-case; customers may type any case")
    name = models.CharField(max_length=100, help_text="Internal note and the label shown on the order")
    kind = models.CharField(max_length=20, choices=Kind.choices)
    value = models.PositiveIntegerField(help_text="Percent (1-90), satang off the order, or 1 for free shipping (unused)")
    max_discount_satang = models.PositiveIntegerField(null=True, blank=True, help_text="Cap for percent coupons")
    min_subtotal_satang = models.PositiveIntegerField(default=0, help_text="Goods total needed to use the code")
    exclude_discounted_items = models.BooleanField(default=False, help_text="Items already on promotion do not count and are not discounted again")
    usage_limit = models.PositiveIntegerField(null=True, blank=True, help_text="Total uses across all customers; empty = unlimited")
    per_phone_limit = models.PositiveSmallIntegerField(null=True, blank=True, default=1, help_text="Uses per customer phone number; empty = unlimited")
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(condition=Q(value__gt=0), name="coupon_value_positive"),
            models.CheckConstraint(condition=~Q(kind="percent") | Q(value__lte=90), name="coupon_percent_at_most_90"),
            models.CheckConstraint(condition=Q(ends_at__isnull=True) | Q(ends_at__gt=F("starts_at")), name="coupon_ends_after_start"),
        ]

    @property
    def label(self) -> str:
        if self.kind == self.Kind.FREE_SHIPPING:
            return "ส่งฟรี"
        if self.kind == self.Kind.PERCENT:
            return f"ลด {self.value}%" + (f" (สูงสุด ฿{self.max_discount_satang / 100:,.0f})" if self.max_discount_satang else "")
        baht = self.value / 100
        return f"ลด ฿{baht:,.0f}" if self.value % 100 == 0 else f"ลด ฿{baht:,.2f}"

    def is_live(self, at=None) -> bool:
        at = at or timezone.now()
        return self.is_active and self.starts_at <= at and (self.ends_at is None or self.ends_at > at)

    def __str__(self) -> str:
        return self.code


class CouponRedemption(models.Model):
    """One use of a coupon on one order. released_at is set when the order is cancelled, which frees the use."""

    coupon = models.ForeignKey(Coupon, on_delete=models.PROTECT, related_name="redemptions")
    order = models.OneToOneField("orders.Order", on_delete=models.CASCADE, related_name="coupon_redemption")
    phone = models.CharField(max_length=10, db_index=True)
    discount_satang = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    released_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["coupon", "released_at"])]
