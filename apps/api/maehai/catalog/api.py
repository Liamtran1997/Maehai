"""Public, read-only catalog for the shop."""
from urllib.parse import quote

from django.conf import settings
from django.http import Http404
from ninja import Router

from maehai.inventory.services import available_map

from .models import Category, Product
from .pricing import Price, prices_for
from .schemas import CategoryOut, ProductListOut, ProductOut

router = Router(tags=["catalog"])

RESTOCK_PREFIX = "แจ้งเตือนสินค้า"   # the LINE webhook recognises "<prefix> <sku>"


def _image_urls(request, product: Product) -> list[dict]:
    return [{"id": im.id, "url": request.build_absolute_uri(im.image.url)} for im in product.images.all()]


def _primary_url(request, product: Product) -> str | None:
    imgs = _image_urls(request, product)
    return imgs[0]["url"] if imgs else None


def restock_alert_url(sku: str) -> str | None:
    if not (settings.LINE_OA_ID and settings.LINE_CHANNEL_ACCESS_TOKEN):
        return None  # without a working OA the button would lead nowhere
    return f"https://line.me/R/oaMessage/{settings.LINE_OA_ID}/?{quote(f'{RESTOCK_PREFIX} {sku}')}"


def _active(p: Product):
    return [v for v in p.variants.all() if v.is_active]


def serialize_list(request, p: Product, amap: dict, prices: dict[int, Price]) -> dict:
    variants = _active(p)
    cheapest = min(variants, key=lambda v: prices[v.id].satang) if variants else None
    best = max((prices[v.id] for v in variants), key=lambda x: x.list_satang - x.satang, default=None)
    cp = prices[cheapest.id] if cheapest else None
    return {
        "in_stock": any(amap.get(v.id) is None or amap[v.id] > 0 for v in variants),
        "slug": p.slug, "name": p.name, "subtitle": p.subtitle, "category": p.category,
        "badge": p.badge, "bands": p.bands, "image_url": _primary_url(request, p),
        "price_from_satang": cp.satang if cp else 0,
        "original_price_from_satang": cp.list_satang if cp and cp.discounted else None,
        "promotion_label": best.promotion.label if best and best.discounted else None,
    }


def serialize_detail(request, p: Product, *, admin: bool = False) -> dict:
    """admin=True returns LIST prices in price_satang (what staff edit) instead of today's selling price."""
    variants = _active(p)
    amap = available_map(v.id for v in variants)
    prices = prices_for(variants)
    out_variants = []
    for v in variants:
        pr = prices[v.id]
        out_variants.append({
            "id": v.id, "label": v.label, "sku": v.sku, "weight_grams": v.weight_grams, "available": amap.get(v.id),
            "price_satang": pr.list_satang if admin else pr.satang,
            "original_price_satang": pr.list_satang if pr.discounted else None,
            "promotion_label": pr.promotion.label if pr.discounted else None,
            "restock_alert_url": restock_alert_url(v.sku) if (not admin and amap.get(v.id) == 0) else None,
        })
    promo = next((prices[v.id].promotion for v in variants if prices[v.id].discounted), None)
    return {
        **serialize_list(request, p, amap, prices),
        "description": p.description, "fda_number": p.fda_number, "storage_note": p.storage_note,
        "variants": out_variants, "images": _image_urls(request, p),
        "promotion": {"name": promo.name, "label": promo.label, "ends_at": promo.ends_at.isoformat() if promo.ends_at else None} if promo else None,
    }


@router.get("/categories", response=list[CategoryOut])
def list_categories(request):
    return Category.objects.filter(is_active=True, products__is_active=True, products__variants__is_active=True).distinct()


@router.get("/products", response=list[ProductListOut])
def list_products(request, category: str | None = None, q: str | None = None, featured: bool = False):
    qs = Product.objects.visible().with_price_from().select_related("category").prefetch_related("variants", "images")
    if category:
        qs = qs.filter(category__slug=category)
    if q:
        qs = qs.filter(name__icontains=q)
    if featured:
        qs = qs.filter(is_featured=True)
    products = list(qs)
    variants = [v for p in products for v in _active(p)]
    amap = available_map(v.id for v in variants)    # one query for the whole page
    prices = prices_for(variants)                   # one promotions query for the whole page
    return [serialize_list(request, p, amap, prices) for p in products]


@router.get("/products/{slug}", response=ProductOut)
def get_product(request, slug: str):
    p = Product.objects.visible().select_related("category").prefetch_related("variants", "images").filter(slug=slug).first()
    if p is None:
        raise Http404
    return serialize_detail(request, p)
