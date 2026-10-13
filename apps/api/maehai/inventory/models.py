from django.db import models
from django.db.models import F, Q


class Branch(models.Model):
    """A place that holds stock. Exactly one is the central warehouse: it receives goods from sources and supplies
    the other branches by transfer slip. Others only receive from the central warehouse."""

    class Kind(models.TextChoices):
        CENTRAL = "central", "คลังกลาง"
        STORE = "store", "สาขา"

    code = models.SlugField(unique=True)
    name = models.CharField(max_length=100)
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.STORE)
    line_group_id = models.CharField(max_length=64, blank=True, help_text="LINE group for this place's staff alerts. Empty = the shared staff group")
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
        TRANSFER_CANCEL = "transfer_cancel", "ยกเลิกการส่ง (คืนเข้าคลัง)"
        RETURN_IN = "return_in", "รับคืนจากสาขา"
        RETURN_OUT = "return_out", "สาขาส่งคืนคลัง"

    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="movements")
    variant = models.ForeignKey("catalog.ProductVariant", on_delete=models.PROTECT, related_name="movements")
    delta = models.IntegerField()
    on_hand_after = models.PositiveIntegerField()
    reason = models.CharField(max_length=20, choices=Reason.choices)
    note = models.CharField(max_length=200, blank=True)
    order = models.ForeignKey("orders.Order", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    document = models.ForeignKey("inventory.Document", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
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



# ---------------------------------------------------------------- warehouse v2: materials, sources, documents

class Source(models.Model):
    """Where goods come from when they enter the central warehouse (a supplier, or the shop's own kitchen)."""

    class Kind(models.TextChoices):
        MADE = "made", "ผลิตเอง"
        BUY = "buy", "ซื้อ"
        OTHER = "other", "อื่นๆ"

    name = models.CharField(max_length=100)
    kind = models.CharField(max_length=10, choices=Kind.choices)
    phone = models.CharField(max_length=30, blank=True)
    note = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Material(models.Model):
    """A stock item that is not a sellable size: ingredients, packaging and other supplies. Quantities may have
    up to three decimals. The unit is fixed once the item has any movement."""

    class Kind(models.TextChoices):
        MATERIAL = "material", "วัตถุดิบ"
        SUPPLY = "supply", "วัสดุ/บรรจุภัณฑ์"
        OTHER = "other", "อื่นๆ"

    code = models.SlugField(unique=True, max_length=60)
    name = models.CharField(max_length=120)
    kind = models.CharField(max_length=10, choices=Kind.choices)
    unit = models.CharField(max_length=20, help_text="ชิ้น, กก., กรัม, ลิตร, แพ็ค, ม้วน, ถุง…")
    low_stock_threshold = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    note = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["kind", "name"]

    def __str__(self) -> str:
        return self.name


class MaterialLevel(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="material_levels")
    material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name="levels")
    on_hand = models.DecimalField(max_digits=12, decimal_places=3, default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["branch", "material"], name="one_material_level_per_branch"),
            models.CheckConstraint(condition=Q(on_hand__gte=0), name="material_on_hand_not_negative"),
        ]


class MaterialMovement(models.Model):
    """Append-only history of material on hand, the twin of StockMovement."""

    class Reason(models.TextChoices):
        OPENING = "opening", "ยอดยกมา"
        RECEIVE = "receive", "รับเข้าจากแหล่งสินค้า"
        TRANSFER_IN = "transfer_in", "รับโอนจากคลังกลาง"
        TRANSFER_OUT = "transfer_out", "โอนออกไปสาขา"
        TRANSFER_CANCEL = "transfer_cancel", "ยกเลิกการส่ง (คืนเข้าคลัง)"
        RETURN_IN = "return_in", "รับคืนจากสาขา"
        RETURN_OUT = "return_out", "สาขาส่งคืนคลัง"
        CONSUME = "consume", "เบิกใช้"
        WASTE = "waste", "ของเสีย/หมดอายุ"
        COUNT = "count", "นับสต็อก"
        CORRECTION = "correction", "แก้ไขรายการผิด"

    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="material_movements")
    material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name="movements")
    delta = models.DecimalField(max_digits=12, decimal_places=3)
    on_hand_after = models.DecimalField(max_digits=12, decimal_places=3)
    reason = models.CharField(max_length=20, choices=Reason.choices)
    note = models.CharField(max_length=200, blank=True)
    document = models.ForeignKey("inventory.Document", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    actor = models.CharField(max_length=80)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]
        indexes = [models.Index(fields=["material", "-id"]), models.Index(fields=["branch", "-id"])]


class Document(models.Model):
    """A slip that moves goods between places. One table for all three kinds, so every movement can be traced:
      receipt  IN-  goods from a source into the central warehouse (done at once)
      transfer TR-  central warehouse -> one branch (sent, then confirmed or refused by the branch)
      return   RT-  goods coming back to the central warehouse (refused by a branch, or sent back by a branch)
    """

    class Kind(models.TextChoices):
        RECEIPT = "receipt", "ใบรับสินค้า"
        TRANSFER = "transfer", "ใบส่งสินค้า"
        RETURN = "return", "ใบคืนสินค้า"
        COUNT = "count", "ใบนับสต็อก"

    class Status(models.TextChoices):
        POSTED = "posted", "บันทึกแล้ว"
        SENT = "sent", "กำลังส่ง"
        RECEIVED_FULL = "received_full", "รับครบ"
        RECEIVED_PARTIAL = "received_partial", "รับบางส่วน"
        RECEIVED_NONE = "received_none", "ไม่รับทั้งหมด"
        CANCELLED = "cancelled", "ยกเลิก"
        SENT_BACK = "sent_back", "กำลังส่งคืน"
        CLOSED = "closed", "รับคืนแล้ว"
        COUNTING = "counting", "กำลังนับ"
        PENDING_APPROVAL = "pending_approval", "รอการอนุมัติ"

    number = models.CharField(max_length=20, unique=True, blank=True)
    kind = models.CharField(max_length=10, choices=Kind.choices)
    status = models.CharField(max_length=20, choices=Status.choices)
    from_branch = models.ForeignKey(Branch, on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    to_branch = models.ForeignKey(Branch, on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    source = models.ForeignKey(Source, on_delete=models.PROTECT, null=True, blank=True, related_name="documents")
    origin = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True, related_name="returns",
                               help_text="For a return slip: the transfer whose refused goods it carries")
    supplier_ref = models.CharField(max_length=60, blank=True, help_text="Supplier's own bill or delivery number")
    vehicle = models.CharField(max_length=100, blank=True)
    carrier = models.CharField(max_length=100, blank=True, help_text="Driver or person carrying the goods")
    note = models.CharField(max_length=500, blank=True)
    cancel_reason = models.CharField(max_length=300, blank=True)
    review_note = models.CharField(max_length=300, blank=True, help_text="Count slips: why a count was sent back")
    created_by = models.CharField(max_length=80)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.CharField(max_length=80, blank=True, help_text="Who confirmed the arrival")
    closed_at = models.DateTimeField(null=True, blank=True)
    substitute_reason = models.CharField(max_length=300, blank=True, help_text="Set when someone other than the branch's own manager confirmed")
    overdue_alerted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-id"]
        indexes = [models.Index(fields=["kind", "status"]), models.Index(fields=["to_branch", "status"])]

    def __str__(self) -> str:
        return self.number or f"#{self.pk}"


class DocumentLine(models.Model):
    """One item on a slip. Exactly one of variant (a sellable size) or material is set.

    Quantities:
      sent      what left the sending place
      received  what the receiving place put on its shelf
      refused   sent - received - missing; goes back on a return slip
      missing   lost on the way (never comes back)
      discarded (return slips) refused goods that were thrown away at the central warehouse
    """

    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="lines")
    variant = models.ForeignKey("catalog.ProductVariant", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    material = models.ForeignKey(Material, on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    sent = models.DecimalField(max_digits=12, decimal_places=3)
    received = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    refused = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    missing = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    discarded = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    restocked = models.DecimalField(max_digits=12, decimal_places=3, default=0, help_text="Return slips: refused goods put back on the shelf")
    refuse_reason = models.CharField(max_length=20, blank=True, help_text="damaged | wrong | other (refused), missing (lost)")
    refuse_note = models.CharField(max_length=300, blank=True)
    unit_cost_satang = models.PositiveIntegerField(null=True, blank=True, help_text="Optional: cost per unit when received from a source")
    expected = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True, help_text="Count slips: on hand when the counter's figure was saved")
    counted = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True, help_text="Count slips: what the counter found")
    counted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(Q(variant__isnull=False, material__isnull=True) | Q(variant__isnull=True, material__isnull=False)),
                name="document_line_one_item"),
        ]

    @property
    def item_name(self) -> str:
        if self.variant_id:
            return f"{self.variant.product.name} ({self.variant.label})"
        return self.material.name
