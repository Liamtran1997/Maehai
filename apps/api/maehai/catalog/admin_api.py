"""Staff-only catalog management for the back office: products, images, categories, promotions."""
import uuid
from datetime import datetime

from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404
from django.utils import timezone
from ninja import Field, File, Router, Schema
from ninja.errors import HttpError
from ninja.files import UploadedFile
from PIL import Image, UnidentifiedImageError

from maehai.core.auth import staff_auth

from .api import serialize_detail
from .models import Category, Product, Promotion
from .schemas import AdminProductOut, ProductIn
from .services import save_product

router = Router(tags=["admin-catalog"], auth=staff_auth)

IMAGE_TYPES = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}
IMAGE_MAX_BYTES = 5 * 1024 * 1024


def _qs():
    return Product.objects.select_related("category").prefetch_related("variants").order_by("sort_order", "name")


def _admin_out(request, p: Product) -> dict:
    return {**serialize_detail(request, p, admin=True), "id": p.id, "is_active": p.is_active,
            "is_featured": p.is_featured, "sort_order": p.sort_order, "name_en": p.name_en}


# ---------------------------------------------------------------- products
@router.get("/products", response=list[AdminProductOut])
def list_products(request):
    return [_admin_out(request, p) for p in _qs()]


@router.post("/products", response={201: AdminProductOut})
def create_product(request, data: ProductIn):
    return 201, _admin_out(request, _qs().get(pk=save_product(data).pk))


@router.put("/products/{product_id}", response=AdminProductOut)
def update_product(request, product_id: int, data: ProductIn):
    p = save_product(data, get_object_or_404(Product, pk=product_id))
    return _admin_out(request, _qs().get(pk=p.pk))


@router.delete("/products/{product_id}", response={204: None})
def archive_product(request, product_id: int):
    """Soft delete: hide from the shop, keep rows so past orders still resolve."""
    Product.objects.filter(pk=product_id).update(is_active=False)
    return 204, None


@router.post("/products/{product_id}/image", response=AdminProductOut)
def upload_image(request, product_id: int, image: File[UploadedFile]):
    """Replace the product photo. The file is opened with Pillow, so a renamed non-image is refused."""
    p = get_object_or_404(Product, pk=product_id)
    if image.size > IMAGE_MAX_BYTES:
        raise HttpError(422, "รูปใหญ่เกิน 5 MB")
    try:
        with Image.open(image) as im:
            fmt = im.format
            im.verify()
    except (UnidentifiedImageError, OSError):
        raise HttpError(422, "ไฟล์นี้ไม่ใช่รูปภาพ") from None
    if fmt not in IMAGE_TYPES:
        raise HttpError(422, "รองรับเฉพาะ JPG, PNG หรือ WebP")
    image.seek(0)
    old = p.image.name if p.image else None
    p.image.save(f"{uuid.uuid4().hex}{IMAGE_TYPES[fmt]}", image, save=True)
    if old:
        p.image.storage.delete(old)
    return _admin_out(request, _qs().get(pk=p.pk))


@router.delete("/products/{product_id}/image", response=AdminProductOut)
def delete_image(request, product_id: int):
    p = get_object_or_404(Product, pk=product_id)
    if p.image:
        p.image.delete(save=True)
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


@router.get("/categories", response=list[AdminCategoryOut])
def list_categories(request):
    """Every category, hidden ones and empty ones included (the public list hides those)."""
    # order_by is explicit: Django drops Meta.ordering from GROUP BY (annotate + Count) queries.
    return [_cat_out(c) for c in Category.objects.annotate(n=Count("products")).order_by("sort_order", "name")]


@router.post("/categories", response={201: AdminCategoryOut})
def create_category(request, data: CategoryIn):
    if Category.objects.filter(slug=data.slug).exists():
        raise HttpError(409, "slug นี้ถูกใช้แล้ว")
    return 201, _cat_out(Category.objects.create(**data.dict()))


@router.put("/categories/{category_id}", response=AdminCategoryOut)
def update_category(request, category_id: int, data: CategoryIn):
    c = get_object_or_404(Category, pk=category_id)
    if Category.objects.filter(slug=data.slug).exclude(pk=c.pk).exists():
        raise HttpError(409, "slug นี้ถูกใช้แล้ว")
    for k, v in data.dict().items():
        setattr(c, k, v)
    c.save()
    return _cat_out(c)


@router.delete("/categories/{category_id}", response={204: None})
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


@router.get("/promotions", response=list[PromotionOut])
def list_promotions(request):
    return [_promo_out(p) for p in Promotion.objects.prefetch_related("products", "categories")]


@router.post("/promotions", response={201: PromotionOut})
def create_promotion(request, data: PromotionIn):
    return 201, _promo_out(_save_promotion(data, None, request.user.get_username()))


@router.put("/promotions/{promotion_id}", response=PromotionOut)
def update_promotion(request, promotion_id: int, data: PromotionIn):
    p = get_object_or_404(Promotion, pk=promotion_id)
    return _promo_out(_save_promotion(data, p, request.user.get_username()))


@router.post("/promotions/{promotion_id}/end", response=PromotionOut)
def end_promotion(request, promotion_id: int):
    """Stop a running promotion now. Keeps the record (orders already store the name and price they were sold at)."""
    p = get_object_or_404(Promotion, pk=promotion_id)
    now = timezone.now()
    if p.starts_at > now:
        p.is_active = False
    elif not p.ends_at or p.ends_at > now:
        p.ends_at = now
    p.save()
    return _promo_out(p)


@router.delete("/promotions/{promotion_id}", response={204: None})
def delete_promotion(request, promotion_id: int):
    p = get_object_or_404(Promotion, pk=promotion_id)
    if p.starts_at <= timezone.now() and p.is_active:
        raise HttpError(409, "โปรโมชันนี้เริ่มแล้ว ใช้ “ปิดโปรโมชัน” แทนการลบ เพื่อเก็บประวัติไว้")
    p.delete()
    return 204, None

