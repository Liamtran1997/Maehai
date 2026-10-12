import secrets

from django.db import models
from django.db.models import Q
from django.utils import timezone

from maehai.catalog.models import ProductVariant
from maehai.shipping.models import ShippingMethod


class OrderStatus(models.TextChoices):
    PENDING_QUOTE = "pending_quote", "รอร้านแจ้งค่าจัดส่ง"
    WAITING_PAYMENT = "waiting_payment", "รอชำระเงิน"
    PAID = "paid", "ชำระแล้ว"
    PACKING = "packing", "กำลังจัดเตรียม"
    SHIPPED = "shipped", "จัดส่งแล้ว"
    DONE = "done", "สำเร็จ"
    CANCELLED = "cancelled", "ยกเลิก"


# Allowed moves. Money states (PENDING_QUOTE, WAITING_PAYMENT -> PAID) are driven by quoting and payment confirmation.
TRANSITIONS: dict[str, set[str]] = {
    OrderStatus.PENDING_QUOTE: {OrderStatus.WAITING_PAYMENT, OrderStatus.CANCELLED},
    OrderStatus.WAITING_PAYMENT: {OrderStatus.PAID, OrderStatus.CANCELLED},
    OrderStatus.PAID: {OrderStatus.PACKING, OrderStatus.CANCELLED},
    OrderStatus.PACKING: {OrderStatus.SHIPPED, OrderStatus.DONE, OrderStatus.CANCELLED},
    OrderStatus.SHIPPED: {OrderStatus.DONE},
    OrderStatus.DONE: set(),
    OrderStatus.CANCELLED: set(),
}


def new_token() -> str:
    return secrets.token_urlsafe(18)


def new_link_code() -> str:
    """Short code the customer sends to the LINE OA to connect their LINE account to this order."""
    return "".join(secrets.choice("ABCDEFGHJKMNPQRSTUVWXYZ23456789") for _ in range(8))


class Order(models.Model):
    number = models.CharField(max_length=20, unique=True, blank=True)
    public_token = models.CharField(max_length=40, unique=True, default=new_token, editable=False)
    status = models.CharField(max_length=20, choices=OrderStatus.choices, default=OrderStatus.PENDING_QUOTE)

    customer_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=10, help_text="Digits only, Thai mobile or landline")
    line_user_id = models.CharField(max_length=64, blank=True)
    line_link_code = models.CharField(max_length=8, default=new_link_code, editable=False)

    shipping_method = models.ForeignKey(ShippingMethod, on_delete=models.PROTECT)
    fulfillment_branch = models.ForeignKey("inventory.Branch", null=True, blank=True, on_delete=models.PROTECT, related_name="+", help_text="Branch whose stock fills this order")
    requested_date = models.DateField()
    address_line = models.CharField(max_length=300, blank=True)
    subdistrict = models.CharField(max_length=80, blank=True)
    district = models.CharField(max_length=80, blank=True)
    province = models.CharField(max_length=80, blank=True)
    postal_code = models.CharField(max_length=5, blank=True)
    note = models.CharField(max_length=300, blank=True)

    # Money, integer satang. total = subtotal + shipping_fee. VAT is the portion already inside total (0 if not VAT registered).
    subtotal_satang = models.PositiveIntegerField()
    shipping_fee_satang = models.PositiveIntegerField(null=True, blank=True, help_text="null = not quoted yet")
    vat_satang = models.PositiveIntegerField(default=0)
    tracking_ref = models.CharField("เลขพัสดุ/ใบฝากส่ง", max_length=60, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-id"]
        constraints = [
            models.CheckConstraint(condition=Q(subtotal_satang__gt=0), name="order_subtotal_positive"),
        ]
        indexes = [models.Index(fields=["status", "-id"]), models.Index(fields=["phone"])]

    @property
    def total_satang(self) -> int | None:
        return None if self.shipping_fee_satang is None else self.subtotal_satang + self.shipping_fee_satang

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.number:
            be_year = timezone.localtime(self.created_at).year + 543
            self.number = f"MH-{be_year}-{self.pk:06d}"
            super().save(update_fields=["number"])

    def __str__(self) -> str:
        return self.number


class OrderItem(models.Model):
    """Snapshot of what was sold. Names and prices are copied so later catalog edits never change old orders."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    variant = models.ForeignKey(ProductVariant, on_delete=models.PROTECT, related_name="+")
    product_name = models.CharField(max_length=150)
    variant_label = models.CharField(max_length=60)
    sku = models.CharField(max_length=40)
    unit_price_satang = models.PositiveIntegerField()
    quantity = models.PositiveSmallIntegerField()

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(quantity__gt=0), name="item_quantity_positive")]

    @property
    def line_total_satang(self) -> int:
        return self.unit_price_satang * self.quantity


class OrderEvent(models.Model):
    """Audit trail: who changed what, when."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="events")
    created_at = models.DateTimeField(auto_now_add=True)
    actor = models.CharField(max_length=80, default="customer")
    kind = models.CharField(max_length=30)
    detail = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["id"]
