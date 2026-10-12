import uuid
from pathlib import Path

from django.db import models
from django.db.models import F, Min, Q

from maehai.core.storage import product_storage


class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True, help_text="Hidden categories and their products disappear from the shop")

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
        return self.filter(is_active=True, category__is_active=True, variants__is_active=True).distinct()

    def with_price_from(self):
        # order_by is explicit on purpose: Django drops Meta.ordering from GROUP BY queries, and Postgres
        # then returns rows in arbitrary order (SQLite happens to return them by id).
        return self.annotate(price_from_satang=Min("variants__price_satang", filter=Q(variants__is_active=True))).order_by("sort_order", "name")


class Product(models.Model):
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    slug = models.SlugField(max_length=120, unique=True)
    name = models.CharField(max_length=150)
    name_en = models.CharField(max_length=150, blank=True)
    subtitle = models.CharField(max_length=150, blank=True)
    description = models.TextField(blank=True)
    bands = models.JSONField(default=list, blank=True, help_text="List of Band values, e.g. ['yellow','red']")
    badge = models.CharField(max_length=20, choices=Badge.choices, blank=True, default=Badge.NONE)
    fda_number = models.CharField("เลข อย.", max_length=40, blank=True)
    storage_note = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False, help_text="Shown in the home page's best-sellers row")
    sort_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ProductQuerySet.as_manager()

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self) -> str:
        return self.name


def product_image_path(instance, filename: str) -> str:
    """products/<product id>/<year>/<month>/<random>.<ext>: one folder per product, and per month within it,
    so no folder ever holds more than a product's own photos for a month."""
    from django.utils import timezone

    now = timezone.now()
    return f"products/{instance.product_id}/{now:%Y}/{now:%m}/{uuid.uuid4().hex}{Path(filename).suffix.lower()[:5]}"


class ProductImage(models.Model):
    """A photo of a product. The first one by sort_order is the main photo shown in the shop's grid."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to=product_image_path, storage=product_storage)
    sort_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sort_order", "id"]


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


class Promotion(models.Model):
    """A time-boxed discount on products, whole categories, or everything.

    Rules (see docs/specs/product-management.md):
      - Never stacked: when several promotions cover a variant, the customer gets the single biggest discount.
      - A discount that would make the price 0 or less is ignored, never applied.
      - Percent discounts round half up to the satang.
    """

    class Kind(models.TextChoices):
        PERCENT = "percent", "ลดเป็นเปอร์เซ็นต์"
        AMOUNT = "amount", "ลดเป็นจำนวนเงิน"

    class Scope(models.TextChoices):
        PRODUCTS = "products", "สินค้าที่เลือก"
        CATEGORIES = "categories", "ทั้งหมวดหมู่"
        ALL = "all", "สินค้าทุกชิ้น"

    name = models.CharField(max_length=100, help_text="Shown to customers, e.g. ลดรับสงกรานต์")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    value = models.PositiveIntegerField(help_text="Percent (1-90) or satang off per unit")
    scope = models.CharField(max_length=12, choices=Scope.choices)
    products = models.ManyToManyField(Product, blank=True, related_name="promotions")
    categories = models.ManyToManyField(Category, blank=True, related_name="promotions")
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField(null=True, blank=True, help_text="Empty = until switched off")
    is_active = models.BooleanField(default=True)
    created_by = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-starts_at", "-id"]
        constraints = [
            models.CheckConstraint(condition=Q(value__gt=0), name="promotion_value_positive"),
            models.CheckConstraint(condition=~Q(kind="percent") | Q(value__lte=90), name="promotion_percent_at_most_90"),
            models.CheckConstraint(condition=Q(ends_at__isnull=True) | Q(ends_at__gt=F("starts_at")), name="promotion_ends_after_start"),
        ]

    def discount_for(self, list_price: int) -> int:
        """Satang off one unit at this list price. 0 when the promotion would make the item free or negative."""
        if self.kind == self.Kind.PERCENT:
            off = (list_price * self.value + 50) // 100
        else:
            off = self.value
        return off if 0 < off < list_price else 0

    @property
    def label(self) -> str:
        if self.kind == self.Kind.PERCENT:
            return f"ลด {self.value}%"
        baht = self.value / 100
        return f"ลด ฿{baht:,.0f}" if self.value % 100 == 0 else f"ลด ฿{baht:,.2f}"

    def __str__(self) -> str:
        return self.name
