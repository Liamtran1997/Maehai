from django.db import models
from django.db.models import F, Q


class Branch(models.Model):
    code = models.SlugField(unique=True)
    name = models.CharField(max_length=100)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self) -> str:
        return self.name


class StockLevel(models.Model):
    """Units of one variant at one branch. available = on_hand - reserved.
    on_hand is physical stock. reserved is promised to unshipped orders."""

    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="levels")
    variant = models.ForeignKey("catalog.ProductVariant", on_delete=models.CASCADE, related_name="stock_levels")
    on_hand = models.PositiveIntegerField(default=0)
    reserved = models.PositiveIntegerField(default=0)
    online_quota = models.PositiveIntegerField(
        null=True, blank=True, help_text="Most units online may sell from this branch per day. Empty = no daily limit, sell what is on hand.")
    low_stock_threshold = models.PositiveIntegerField(
        null=True, blank=True, help_text="Staff are told when available drops to this. Empty = LOW_STOCK_THRESHOLD.")
    low_alerted = models.BooleanField(default=False, help_text="A low-stock alert is out; cleared once stock is back above the line.")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["branch", "variant"], name="one_level_per_branch_variant"),
            # The database itself refuses to promise more than exists.
            models.CheckConstraint(condition=Q(reserved__lte=F("on_hand")), name="reserved_within_on_hand"),
        ]

    @property
    def available(self) -> int:
        return self.on_hand - self.reserved

    @property
    def threshold(self) -> int:
        from django.conf import settings

        return settings.LOW_STOCK_THRESHOLD if self.low_stock_threshold is None else self.low_stock_threshold

    def online_available(self, sold_today: int) -> int:
        """What the shop may still sell today: the stock, capped by what is left of the daily online quota."""
        if self.online_quota is None:
            return self.available
        return max(0, min(self.available, self.online_quota - sold_today))


class OnlineSale(models.Model):
    """Units reserved by online orders from one level on one day, counted against its daily online quota."""

    level = models.ForeignKey(StockLevel, on_delete=models.CASCADE, related_name="online_sales")
    day = models.DateField()
    units = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["level", "day"], name="one_online_sale_row_per_day")]


class StockMovement(models.Model):
    """Append-only history of every change to on_hand: who, why, how many."""

    class Reason(models.TextChoices):
        RECEIVE = "receive", "รับของเข้า"
        WASTE = "waste", "ของเสีย/หมดอายุ"
        COUNT = "count", "นับสต็อก"
        TRANSFER_IN = "transfer_in", "รับโอน"
        TRANSFER_OUT = "transfer_out", "โอนออก"
        SALE = "sale", "ขาย"
        OPENING = "opening", "ยอดยกมา"
        COUNTER_SALE = "counter_sale", "ขายหน้าร้าน"

    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="movements")
    variant = models.ForeignKey("catalog.ProductVariant", on_delete=models.PROTECT, related_name="movements")
    delta = models.IntegerField()
    on_hand_after = models.PositiveIntegerField()
    reason = models.CharField(max_length=20, choices=Reason.choices)
    note = models.CharField(max_length=200, blank=True)
    order = models.ForeignKey("orders.Order", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    actor = models.CharField(max_length=80)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]
        indexes = [models.Index(fields=["variant", "-id"]), models.Index(fields=["branch", "-id"])]


class StockReservation(models.Model):
    """What an order has set aside. reserved -> committed when the goods leave (shipped/handed over),
    or reserved -> released when the order is cancelled."""

    class State(models.TextChoices):
        RESERVED = "reserved", "จองไว้"
        COMMITTED = "committed", "ตัดสต็อกแล้ว"
        RELEASED = "released", "คืนสต็อก"

    order = models.ForeignKey("orders.Order", on_delete=models.CASCADE, related_name="reservations")
    variant = models.ForeignKey("catalog.ProductVariant", on_delete=models.PROTECT, related_name="+")
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="+")
    quantity = models.PositiveIntegerField()
    state = models.CharField(max_length=10, choices=State.choices, default=State.RESERVED)
    quota_day = models.DateField(null=True, blank=True, help_text="Day whose online quota this reservation was counted against")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["order", "state"])]


class RestockRequest(models.Model):
    """A customer asked (through LINE) to be told when a sold-out variant is back. Notified once, then closed."""

    variant = models.ForeignKey("catalog.ProductVariant", on_delete=models.CASCADE, related_name="restock_requests")
    line_user_id = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    notified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["variant", "line_user_id"], condition=Q(notified_at__isnull=True),
                                               name="one_open_restock_request")]
