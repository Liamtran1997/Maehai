"""Public, read-only catalog for the shop."""
from django.http import Http404
from ninja import Router

from maehai.inventory.services import available_map

from .models import Category, Product
from .schemas import CategoryOut, ProductListOut, ProductOut

router = Router(tags=["catalog"])


def _image_url(request, product: Product) -> str | None:
    return request.build_absolute_uri(product.image.url) if product.image else None


def _in_stock(p: Product, amap: dict) -> bool:
    return any(amap.get(v.id) is None or amap[v.id] > 0 for v in p.variants.all() if v.is_active)


def serialize_list(request, p: Product, amap: dict | None = None) -> dict:
    amap = amap if amap is not None else available_map(v.id for v in p.variants.all())
    return {
        "in_stock": _in_stock(p, amap),
        "slug": p.slug, "name": p.name, "subtitle": p.subtitle, "category": p.category,
        "badge": p.badge, "bands": p.bands, "image_url": _image_url(request, p),
        "price_from_satang": p.price_from_satang,
    }


def serialize_detail(request, p: Product) -> dict:
    amap = available_map(v.id for v in p.variants.all())
    variants = [v for v in p.variants.all() if v.is_active]
    for v in variants:
        v.available = amap.get(v.id)
    return {
        **serialize_list(request, p, amap),
        "description": p.description, "fda_number": p.fda_number, "storage_note": p.storage_note,
        "variants": variants,
    }


@router.get("/categories", response=list[CategoryOut])
def list_categories(request):
    return Category.objects.filter(products__is_active=True, products__variants__is_active=True).distinct()


@router.get("/products", response=list[ProductListOut])
def list_products(request, category: str | None = None, q: str | None = None):
    qs = Product.objects.visible().with_price_from().select_related("category").prefetch_related("variants")
    if category:
        qs = qs.filter(category__slug=category)
    if q:
        qs = qs.filter(name__icontains=q)
    products = list(qs)
    amap = available_map(v.id for p in products for v in p.variants.all())   # one query for the whole page
    return [serialize_list(request, p, amap) for p in products]


@router.get("/products/{slug}", response=ProductOut)
def get_product(request, slug: str):
    p = Product.objects.visible().with_price_from().select_related("category").prefetch_related("variants").filter(slug=slug).first()
    if p is None:
        raise Http404
    return serialize_detail(request, p)
