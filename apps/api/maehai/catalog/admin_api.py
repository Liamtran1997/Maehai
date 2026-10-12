"""Staff-only catalog management for the back office: products, images, categories, promotions."""
import uuid
from datetime import datetime

from django.conf import settings
from django.db import transaction
from django.db.models import Count, Max
from django.shortcuts import get_object_or_404
from django.utils import timezone
from ninja import Field, File, Router, Schema
from ninja.errors import HttpError
from ninja.files import UploadedFile
from PIL import Image, UnidentifiedImageError

from maehai.core.auth import requires
from maehai.core.models import audit
from maehai.core.permissions import check

from .api import serialize_detail
from .models import Category, PriceChange, Product, ProductImage, ProductVariant, Promotion
from .schemas import AdminProductOut, ProductIn
from .services import save_product

router = Router(tags=["admin-catalog"])

IMAGE_TYPES = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}


def _qs():
    return Product.objects.select_related("category").prefetch_related("variants", "images").order_by("sort_order", "name")


def _admin_out(request, p: Product) -> dict:
    return {**serialize_detail(request, p, admin=True), "id": p.id, "is_active": p.is_active,
            "is_featured": p.is_featured, "sort_order": p.sort_order, "name_en": p.name_en}


# ---------------------------------------------------------------- products
def _price_changes(product: Product, data: ProductIn) -> list[str]:
    """Human-readable list of price changes this edit would make (new sizes count as a change)."""
    old = {v.sku: v.price_satang for v in ProductVariant.objects.filter(product=product)}
    out = []
    for v in data.variants:
        if v.sku not in old:
            out.append(f"{v.sku}: เพิ่มขนาด {v.price_satang / 100:g}")
        elif old[v.sku] != v.price_satang:
            out.append(f"{v.sku}: {old[v.sku] / 100:g} → {v.price_satang / 100:g}")
    return out


@router.get("/products", response=list[AdminProductOut], auth=requires("catalog.view"))
def list_products(request):
    return [_admin_out(request, p) for p in _qs()]


@router.post("/products", response={201: AdminProductOut}, auth=requires("catalog.edit"))
def create_product(request, data: ProductIn):
    check(request, "pricing.manage")        # a new product always sets prices
    p = save_product(data, actor=request.user.get_username())
    audit(request, "product.create", p.slug, ", ".join(f"{v.sku}={v.price_satang / 100:g}" for v in data.variants))
    return 201, _admin_out(request, _qs().get(pk=p.pk))


@router.put("/products/{product_id}", response=AdminProductOut, auth=requires("catalog.edit"))
def update_product(request, product_id: int, data: ProductIn):
    product = get_object_or_404(Product, pk=product_id)
    changes = _price_changes(product, data)
    if changes:
        check(request, "pricing.manage")    # editing text and images is catalog.edit; touching a price is pricing.manage
    p = save_product(data, product, actor=request.user.get_username())
    if changes:
        audit(request, "price.change", p.slug, "; ".join(changes))
    return _admin_out(request, _qs().get(pk=p.pk))


class PriceChangeOut(Schema):
    sku: str
    label: str
    old_price_satang: int | None
    new_price_satang: int
    actor: str
    created_at: datetime


@router.get("/products/{product_id}/price-history", response=list[PriceChangeOut], auth=requires("pricing.manage"))
def price_history(request, product_id: int):
    """Every price change of this product's sizes, newest first. Who changed it and when."""
    p = get_object_or_404(Product, pk=product_id)
    rows = PriceChange.objects.filter(variant__product=p).select_related("variant").order_by("-id")[:200]
    return [{"sku": r.variant.sku, "label": r.variant.label, "old_price_satang": r.old_price_satang,
             "new_price_satang": r.new_price_satang, "actor": r.actor, "created_at": r.created_at} for r in rows]


@router.delete("/products/{product_id}", response={204: None}, auth=requires("catalog.edit"))
def archive_product(request, product_id: int):
    """Soft delete: hide from the shop, keep rows so past orders still resolve."""
    Product.objects.filter(pk=product_id).update(is_active=False)
    return 204, None


MAX_IMAGES = 10


def _check_image(image: UploadedFile) -> str:
    """Refuses anything that is not a real JPG, PNG or WebP within the size limit. Returns the file extension to store."""
    if image.size > settings.IMAGE_MAX_BYTES:
        raise HttpError(422, f"รูปใหญ่เกิน {settings.IMAGE_MAX_MB} MB")
    try:
        with Image.open(image) as im:
            fmt = im.format
            im.verify()
    except (UnidentifiedImageError, OSError):
        raise HttpError(422, "ไฟล์นี้ไม่ใช่รูปภาพ") from None
    if fmt not in IMAGE_TYPES:
        raise HttpError(422, "รองรับเฉพาะ JPG, PNG หรือ WebP")
    image.seek(0)
    return IMAGE_TYPES[fmt]


@router.post("/products/{product_id}/images", response=AdminProductOut, auth=requires("catalog.edit"))
def add_image(request, product_id: int, image: File[UploadedFile]):
    """Adds a photo at the end of the gallery. The first photo is the one customers see in the grid."""
    p = get_object_or_404(Product, pk=product_id)
    if p.images.count() >= MAX_IMAGES:
        raise HttpError(422, f"เพิ่มรูปได้สูงสุด {MAX_IMAGES} รูปต่อสินค้า")
    ext = _check_image(image)
    last = p.images.aggregate(m=Max("sort_order"))["m"]
    im = ProductImage(product=p, sort_order=0 if last is None else last + 1)
    im.image.save(f"{uuid.uuid4().hex}{ext}", image, save=True)
    return _admin_out(request, _qs().get(pk=p.pk))


@router.delete("/products/{product_id}/images/{image_id}", response=AdminProductOut, auth=requires("catalog.edit"))
def delete_image(request, product_id: int, image_id: int):
    im = get_object_or_404(ProductImage, pk=image_id, product_id=product_id)
    name = im.image.name
    im.delete()
    if name:
        im.image.storage.delete(name)
    return _admin_out(request, _qs().get(pk=product_id))


class ImageOrderIn(Schema):
    ids: list[int] = Field(min_length=1, max_length=MAX_IMAGES)


@router.put("/products/{product_id}/image-order", response=AdminProductOut, auth=requires("catalog.edit"))
@transaction.atomic
def reorder_images(request, product_id: int, data: ImageOrderIn):
    """Set the gallery order. Must list every photo of this product exactly once; the first one becomes the main photo."""
    p = get_object_or_404(Product, pk=product_id)
    current = set(p.images.values_list("id", flat=True))
    if len(set(data.ids)) != len(data.ids) or set(data.ids) != current:
        raise HttpError(422, "ต้องส่งลำดับรูปทุกรูปของสินค้านี้ รูปละครั้ง")
    for position, image_id in enumerate(data.ids):
        ProductImage.objects.filter(pk=image_id, product=p).update(sort_order=position)
    return _admin_out(request, _qs().get(pk=p.pk))


# ---------------------------------------------------------------- categories
class AdminCategoryOut(Schema):
    id: int
    name: str
    slug: str
    sort_order: int
    is_active: bool
    product_count: int


class CategoryIn(Schema):
    name: str = Field(min_length=1, max_length=100)
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=50)
    sort_order: int = Field(default=0, ge=0, le=32767)
    is_active: bool = True


def _cat_out(c: Category) -> dict:
    n = getattr(c, "n", None)
    return {"id": c.id, "name": c.name, "slug": c.slug, "sort_order": c.sort_order, "is_active": c.is_active,
            "product_count": n if n is not None else c.products.count()}


@router.get("/categories", response=list[AdminCategoryOut], auth=requires("catalog.view"))
def list_categories(request):
    """Every category, hidden ones and empty ones included (the public list hides those)."""
    # order_by is explicit: Django drops Meta.ordering from GROUP BY (annotate + Count) queries.
    return [_cat_out(c) for c in Category.objects.annotate(n=Count("products")).order_by("sort_order", "name")]


@router.post("/categories", response={201: AdminCategoryOut}, auth=requires("catalog.edit"))
def create_category(request, data: CategoryIn):
    if Category.objects.filter(slug=data.slug).exists():
        raise HttpError(409, "slug นี้ถูกใช้แล้ว")
    return 201, _cat_out(Category.objects.create(**data.dict()))


@router.put("/categories/{category_id}", response=AdminCategoryOut, auth=requires("catalog.edit"))
def update_category(request, category_id: int, data: CategoryIn):
    c = get_object_or_404(Category, pk=category_id)
    if Category.objects.filter(slug=data.slug).exclude(pk=c.pk).exists():
        raise HttpError(409, "slug นี้ถูกใช้แล้ว")
    for k, v in data.dict().items():
        setattr(c, k, v)
    c.save()
    return _cat_out(c)


@router.delete("/categories/{category_id}", response={204: None}, auth=requires("catalog.edit"))
def delete_category(request, category_id: int):
    c = get_object_or_404(Category, pk=category_id)
    if c.products.exists():
        raise HttpError(409, "หมวดหมู่นี้ยังมีสินค้า ย้ายสินค้าออกก่อน หรือซ่อนหมวดหมู่แทนการลบ")
    c.delete()
    return 204, None


# ---------------------------------------------------------------- promotions
class PromotionIn(Schema):
    name: str = Field(min_length=1, max_length=100)
    kind: str                         # percent | amount
    value: int = Field(gt=0)          # percent, or satang off per unit
    scope: str                        # products | categories | all
    product_ids: list[int] = []
    category_ids: list[int] = []
    starts_at: datetime
    ends_at: datetime | None = None
    is_active: bool = True


class PromotionOut(Schema):
    id: int
    name: str
    kind: str
    value: int
    label: str
    scope: str
    product_ids: list[int]
    category_ids: list[int]
    starts_at: datetime
    ends_at: datetime | None
    is_active: bool
    state: str                        # scheduled | running | ended | off
    warnings: list[str]


def _state(p: Promotion, now) -> str:
    if not p.is_active:
        return "off"
    if p.starts_at > now:
        return "scheduled"
    if p.ends_at and p.ends_at <= now:
        return "ended"
    return "running"


def _warnings(p: Promotion) -> list[str]:
    """Products this promotion cannot discount because the amount is as big as the price (it would be free)."""
    if p.kind != Promotion.Kind.AMOUNT:
        return []
    from .models import ProductVariant

    qs = ProductVariant.objects.filter(is_active=True, price_satang__lte=p.value).select_related("product")
    if p.scope == Promotion.Scope.PRODUCTS:
        qs = qs.filter(product__in=p.products.all())
    elif p.scope == Promotion.Scope.CATEGORIES:
        qs = qs.filter(product__category__in=p.categories.all())
    return [f"{v.product.name} ({v.label}) ราคาไม่มากกว่าส่วนลด จะไม่ถูกลดราคา" for v in qs[:10]]


def _promo_out(p: Promotion) -> dict:
    return {"id": p.id, "name": p.name, "kind": p.kind, "value": p.value, "label": p.label, "scope": p.scope,
            "product_ids": [x.id for x in p.products.all()], "category_ids": [x.id for x in p.categories.all()],
            "starts_at": p.starts_at, "ends_at": p.ends_at, "is_active": p.is_active,
            "state": _state(p, timezone.now()), "warnings": _warnings(p)}


@transaction.atomic
def _save_promotion(data: PromotionIn, p: Promotion | None, actor: str) -> Promotion:
    if data.kind not in Promotion.Kind.values:
        raise HttpError(422, "ประเภทส่วนลดไม่ถูกต้อง")
    if data.scope not in Promotion.Scope.values:
        raise HttpError(422, "ขอบเขตส่วนลดไม่ถูกต้อง")
    if data.kind == Promotion.Kind.PERCENT and not 1 <= data.value <= 90:
        raise HttpError(422, "ลดได้ 1 ถึง 90 เปอร์เซ็นต์")
    if data.ends_at and data.ends_at <= data.starts_at:
        raise HttpError(422, "วันสิ้นสุดต้องอยู่หลังวันเริ่ม")
    products = list(Product.objects.filter(pk__in=data.product_ids))
    categories = list(Category.objects.filter(pk__in=data.category_ids))
    if data.scope == Promotion.Scope.PRODUCTS and not products:
        raise HttpError(422, "เลือกสินค้าอย่างน้อย 1 รายการ")
    if data.scope == Promotion.Scope.CATEGORIES and not categories:
        raise HttpError(422, "เลือกหมวดหมู่อย่างน้อย 1 หมวด")

    fields = data.dict(exclude={"product_ids", "category_ids"})
    if p is None:
        p = Promotion.objects.create(created_by=actor, **fields)
    else:
        for k, v in fields.items():
            setattr(p, k, v)
        p.save()
    p.products.set(products if data.scope == Promotion.Scope.PRODUCTS else [])
    p.categories.set(categories if data.scope == Promotion.Scope.CATEGORIES else [])
    return p


@router.get("/promotions", response=list[PromotionOut], auth=requires("catalog.view"))
def list_promotions(request):
    return [_promo_out(p) for p in Promotion.objects.prefetch_related("products", "categories")]


@router.post("/promotions", response={201: PromotionOut}, auth=requires("pricing.manage"))
def create_promotion(request, data: PromotionIn):
    p = _save_promotion(data, None, request.user.get_username())
    audit(request, "promotion.create", p.name, p.label)
    return 201, _promo_out(p)


@router.put("/promotions/{promotion_id}", response=PromotionOut, auth=requires("pricing.manage"))
def update_promotion(request, promotion_id: int, data: PromotionIn):
    p = _save_promotion(data, get_object_or_404(Promotion, pk=promotion_id), request.user.get_username())
    audit(request, "promotion.update", p.name, p.label)
    return _promo_out(p)


@router.post("/promotions/{promotion_id}/end", response=PromotionOut, auth=requires("pricing.manage"))
def end_promotion(request, promotion_id: int):
    """Stop a running promotion now. Keeps the record (orders already store the name and price they were sold at)."""
    p = get_object_or_404(Promotion, pk=promotion_id)
    now = timezone.now()
    if p.starts_at > now:
        p.is_active = False
    elif not p.ends_at or p.ends_at > now:
        p.ends_at = now
    p.save()
    audit(request, "promotion.end", p.name)
    return _promo_out(p)


@router.delete("/promotions/{promotion_id}", response={204: None}, auth=requires("pricing.manage"))
def delete_promotion(request, promotion_id: int):
    p = get_object_or_404(Promotion, pk=promotion_id)
    if p.starts_at <= timezone.now() and p.is_active:
        raise HttpError(409, "โปรโมชันนี้เริ่มแล้ว ใช้ “ปิดโปรโมชัน” แทนการลบ เพื่อเก็บประวัติไว้")
    audit(request, "promotion.delete", p.name)
    p.delete()
    return 204, None

