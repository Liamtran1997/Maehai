"""Staff-only catalog management for the back office."""
from django.shortcuts import get_object_or_404
from ninja import Router

from maehai.core.auth import staff_auth

from .api import serialize_detail
from .models import Category, Product
from .schemas import AdminProductOut, CategoryOut, ProductIn
from .services import save_product

router = Router(tags=["admin-catalog"], auth=staff_auth)


def _qs():
    return Product.objects.with_price_from().select_related("category").prefetch_related("variants")


def _out(request, p: Product) -> dict:
    p = _qs().get(pk=p.pk)
    return {**serialize_detail(request, p), "id": p.id, "is_active": p.is_active}


@router.get("/categories", response=list[CategoryOut])
def list_categories(request):
    """Every category, including ones with no visible products yet (the public list hides those)."""
    return Category.objects.all()


@router.get("/products", response=list[AdminProductOut])
def list_products(request):
    return [{**serialize_detail(request, p), "id": p.id, "is_active": p.is_active} for p in _qs()]


@router.post("/products", response={201: AdminProductOut})
def create_product(request, data: ProductIn):
    return 201, _out(request, save_product(data))


@router.put("/products/{product_id}", response=AdminProductOut)
def update_product(request, product_id: int, data: ProductIn):
    return _out(request, save_product(data, get_object_or_404(Product, pk=product_id)))


@router.delete("/products/{product_id}", response={204: None})
def archive_product(request, product_id: int):
    """Soft delete: hide from the shop, keep rows so past orders still resolve."""
    Product.objects.filter(pk=product_id).update(is_active=False)
    return 204, None
