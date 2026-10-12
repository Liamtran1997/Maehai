from django.db import models


class ShippingMethod(models.Model):
    """How the customer gets the goods. Fee is free (pickup) or quoted by staff per order."""

    class Kind(models.TextChoices):
        PICKUP = "pickup", "รับที่ร้าน"
        CARRIER = "carrier", "ฝากขนส่ง (รถ/รถไฟ/เครื่องบิน)"
        PARCEL = "parcel", "พัสดุส่งถึงที่"

    code = models.SlugField(unique=True)
    name = models.CharField(max_length=100)
    kind = models.CharField(max_length=10, choices=Kind.choices)
    description = models.CharField(max_length=300, blank=True)
    branch = models.ForeignKey("inventory.Branch", null=True, blank=True, on_delete=models.SET_NULL, related_name="+", help_text="Pickup methods: the branch the customer collects from")
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]

    @property
    def requires_address(self) -> bool:
        return self.kind == self.Kind.PARCEL

    @property
    def fee_is_quoted(self) -> bool:
        """Staff tell the customer the fee after the order is placed (matches how the shop works today)."""
        return self.kind != self.Kind.PICKUP

    def __str__(self) -> str:
        return self.name
