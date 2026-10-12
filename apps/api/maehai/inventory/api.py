"""Staff-only stock management."""
from django.shortcuts import get_object_or_404
from ninja import Field, Router, Schema

from maehai.catalog.models import ProductVariant
from maehai.core.auth import requires

from . import services
from .models import Branch, StockLevel, StockMovement

router = Router(tags=["admin-inventory"])


class BranchOut(Schema):
    code: str
    name: str


class LevelOut(Schema):
    branch: str
    on_hand: int
    reserved: int
    available: int


class StockRowOut(Schema):
    sku: str
    product_name: str
    variant_label: str
    track_stock: bool
    levels: list[LevelOut]


class AdjustIn(Schema):
    branch: str
    sku: str
    reason: str                     # receive | waste | count
    quantity: int = Field(ge=0, le=1_000_000)
    note: str = Field(default="", max_length=200)


class TransferIn(Schema):
    from_branch: str
    to_branch: str
    sku: str
    quantity: int = Field(gt=0, le=1_000_000)
    note: str = Field(default="", max_length=200)


class TrackIn(Schema):
    track: bool


class MovementOut(Schema):
    created_at: str
    branch: str
    sku: str
    product_name: str
    variant_label: str
    delta: int
    on_hand_after: int
    reason: str
    reason_label: str
    note: str
    order_number: str | None
    actor: str


def _branch(code: str) -> Branch:
    return get_object_or_404(Branch, code=code, is_active=True)


def _variant(sku: str) -> ProductVariant:
    return get_object_or_404(ProductVariant.objects.select_related("product"), sku=sku)


@router.get("/branches", response=list[BranchOut], auth=requires("inventory.view"))
def branches(request):
    return Branch.objects.filter(is_active=True)


@router.get("/stock", response=list[StockRowOut], auth=requires("inventory.view"))
def stock(request, q: str | None = None, tracked_only: bool = False):
    qs = ProductVariant.objects.filter(is_active=True, product__is_active=True).select_related("product").prefetch_related("stock_levels__branch")
    if q:
        qs = qs.filter(product__name__icontains=q)
    if tracked_only:
        qs = qs.filter(track_stock=True)
    order = list(Branch.objects.filter(is_active=True).values_list("code", flat=True))
    rows = []
    for v in qs.order_by("product__sort_order", "product__name", "sort_order"):
        by_branch = {lv.branch.code: lv for lv in v.stock_levels.all()}
        rows.append({
            "sku": v.sku, "product_name": v.product.name, "variant_label": v.label, "track_stock": v.track_stock,
            "levels": [{"branch": c, "on_hand": by_branch[c].on_hand if c in by_branch else 0,
                        "reserved": by_branch[c].reserved if c in by_branch else 0,
                        "available": by_branch[c].available if c in by_branch else 0} for c in order],
        })
    return rows


@router.post("/adjust", response=LevelOut, auth=requires("inventory.adjust"))
def adjust(request, data: AdjustIn):
    lv = services.adjust(branch=_branch(data.branch), variant=_variant(data.sku), reason=data.reason,
                         quantity=data.quantity, note=data.note, actor=request.user.get_username())
    return {"branch": data.branch, "on_hand": lv.on_hand, "reserved": lv.reserved, "available": lv.available}


@router.post("/transfer", auth=requires("inventory.adjust"))
def transfer(request, data: TransferIn):
    services.transfer(source=_branch(data.from_branch), dest=_branch(data.to_branch), variant=_variant(data.sku),
                      quantity=data.quantity, note=data.note, actor=request.user.get_username())
    return {"ok": True}


@router.post("/variants/{sku}/track", response=StockRowOut, auth=requires("inventory.adjust"))
def set_tracking(request, sku: str, data: TrackIn):
    v = _variant(sku)
    v.track_stock = data.track
    v.save(update_fields=["track_stock"])
    return next(r for r in stock(request, q=None) if r["sku"] == sku)


@router.get("/movements", response=list[MovementOut], auth=requires("inventory.view"))
def movements(request, sku: str | None = None, branch: str | None = None, limit: int = 50):
    limit = max(1, min(limit, 200))
    qs = StockMovement.objects.select_related("branch", "variant__product", "order")
    if sku:
        qs = qs.filter(variant__sku=sku)
    if branch:
        qs = qs.filter(branch__code=branch)
    return [{
        "created_at": m.created_at.isoformat(), "branch": m.branch.code, "sku": m.variant.sku,
        "product_name": m.variant.product.name, "variant_label": m.variant.label, "delta": m.delta,
        "on_hand_after": m.on_hand_after, "reason": m.reason, "reason_label": m.get_reason_display(), "note": m.note,
        "order_number": m.order.number if m.order else None, "actor": m.actor,
    } for m in qs[:limit]]
