from django.db import models
from django.db.models import Min, Q


class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name_plural = "categories"

    def __str__(self) -> str:
        return self.name


class Band(models.TextChoices):
    """Rubber-band colour tied on a log. Tells the flavour (ยางเหลือง/แดง/เขียว)."""

    YELLOW = "yellow", "ยางเหลือง"
    RED = "red", "ยางแดง"
    GREEN = "green", "ยางเขียว"


class Badge(models.TextChoices):
    NONE = "", "—"
    BEST_SELLER = "best_seller", "ขายดี"
    NEW = "new", "ใหม่"


class ProductQuerySet(models.QuerySet):
    def visible(self):
        """Products the shop may show: active and with at least one active variant."""
        return self.filter(is_active=True, variants__is_active=True).distinct()

    def with_price_from(self):
        return self.annotate(price_from_satang=Min("variants__price_satang", filter=Q(variants__is_active=True)))


class Product(models.Model):
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    slug = models.SlugField(max_length=120, unique=True)
    name = models.CharField(max_length=150)
    name_en = models.CharField(max_length=150, blank=True)
    subtitle = models.CharField(max_length=150, blank=True)
    description = models.TextField(blank=True)
    bands = models.JSONField(default=list, blank=True, help_text="List of Band values, e.g. ['yellow','red']")
    badge = models.CharField(max_length=20, choices=Badge.choices, blank=True, default=Badge.NONE)
    image = models.ImageField(upload_to="products/", blank=True)
    fda_number = models.CharField("เลข อย.", max_length=40, blank=True)
    storage_note = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ProductQuerySet.as_manager()

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self) -> str:
        return self.name


class ProductVariant(models.Model):
    """A sellable size/pack of a product. Price is integer satang (1 THB = 100)."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    label = models.CharField(max_length=60, help_text="เช่น เล็ก, กลาง, ใหญ่, แผ่น")
    sku = models.CharField(max_length=40, unique=True)
    price_satang = models.PositiveIntegerField()
    weight_grams = models.PositiveIntegerField(null=True, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    track_stock = models.BooleanField(default=False, help_text="Off = sold without counting (made to order). Turn on once stock counts are entered.")

    class Meta:
        ordering = ["sort_order", "price_satang"]
        constraints = [
            models.CheckConstraint(condition=Q(price_satang__gt=0), name="variant_price_positive"),
            models.UniqueConstraint(fields=["product", "label"], name="variant_label_unique_per_product"),
        ]

    def __str__(self) -> str:
        return f"{self.product.name} ({self.label})"
