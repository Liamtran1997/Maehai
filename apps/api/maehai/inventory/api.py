"""Staff-only stock management."""
from django.shortcuts import get_object_or_404
from django.utils import timezone
from ninja import Field, Router, Schema

from maehai.catalog.models import ProductVariant
from maehai.core.auth import requires
from maehai.core.models import audit

from . import services
from .models import Branch, OnlineSale, StockLevel, StockMovement

router = Router(tags=["admin-inventory"])


class BranchOut(Schema):
    code: str
    name: str


class LevelOut(Schema):
    branch: str
    on_hand: int
    reserved: int
    available: int
    online_quota: int | None = None          # most the shop may sell from here per day (None = no limit)
    online_sold_today: int = 0
    online_available: int = 0                # what the shop can still sell today
    low_stock_threshold: int | None = None   # this level's own line (None = the shop default)
    low_stock_line: int = 0                  # the line actually used


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


class LevelSettingsIn(Schema):
    branch: str
    sku: str
    online_quota: int | None = Field(default=None, ge=0, le=1_000_000)
    low_stock_threshold: int | None = Field(default=None, ge=0, le=1_000_000)


class SoldOutIn(Schema):
    branch: str
    sku: str
    note: str = Field(default="", max_length=200)


class ImportIn(Schema):
    csv: str = Field(max_length=services.IMPORT_MAX_CHARS)


class ImportRowOut(Schema):
    line: int
    sku: str
    branch_code: str
    tracking: str
    product_name: str
    variant_label: str
    on_hand: int | None
    online_quota: int | None
    low_stock_threshold: int | None
    current_on_hand: int
    delta: int | None
    errors: list[str]


class ImportPreviewOut(Schema):
    rows: list[ImportRowOut]
    total: int
    error_count: int
    ok_count: int


class ImportResultOut(Schema):
    rows: int
    changed: int


class TemplateOut(Schema):
    filename: str
    csv: str


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


def _level_out(code: str, lv: StockLevel | None, sold: int = 0) -> dict:
    if lv is None:
        return {"branch": code, "on_hand": 0, "reserved": 0, "available": 0, "online_quota": None, "online_sold_today": 0,
                "online_available": 0, "low_stock_threshold": None, "low_stock_line": StockLevel(low_stock_threshold=None).threshold}
    return {"branch": code, "on_hand": lv.on_hand, "reserved": lv.reserved, "available": lv.available,
            "online_quota": lv.online_quota, "online_sold_today": sold, "online_available": lv.online_available(sold),
            "low_stock_threshold": lv.low_stock_threshold, "low_stock_line": lv.threshold}


def _sold_today(level_ids) -> dict[int, int]:
    return dict(OnlineSale.objects.filter(level_id__in=level_ids, day=timezone.localdate()).values_list("level_id", "units"))


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
    variants = list(qs.order_by("product__sort_order", "product__name", "sort_order"))
    sold = _sold_today([lv.id for v in variants for lv in v.stock_levels.all()])
    rows = []
    for v in variants:
        by_branch = {lv.branch.code: lv for lv in v.stock_levels.all()}
        rows.append({
            "sku": v.sku, "product_name": v.product.name, "variant_label": v.label, "track_stock": v.track_stock,
            "levels": [_level_out(c, by_branch.get(c), sold.get(by_branch[c].id, 0) if c in by_branch else 0) for c in order],
        })
    return rows


@router.post("/adjust", response=LevelOut, auth=requires("inventory.adjust"))
def adjust(request, data: AdjustIn):
    lv = services.adjust(branch=_branch(data.branch), variant=_variant(data.sku), reason=data.reason,
                         quantity=data.quantity, note=data.note, actor=request.user.get_username())
    return _level_out(data.branch, lv, _sold_today([lv.id]).get(lv.id, 0))


@router.post("/transfer", auth=requires("inventory.adjust"))
def transfer(request, data: TransferIn):
    services.transfer(source=_branch(data.from_branch), dest=_branch(data.to_branch), variant=_variant(data.sku),
                      quantity=data.quantity, note=data.note, actor=request.user.get_username())
    return {"ok": True}


@router.put("/levels", response=LevelOut, auth=requires("inventory.adjust"))
def level_settings(request, data: LevelSettingsIn):
    """Daily online quota and own low-stock line for one size at one branch."""
    v = _variant(data.sku)
    lv = services.set_level_settings(branch=_branch(data.branch), variant=v, online_quota=data.online_quota,
                                     low_stock_threshold=data.low_stock_threshold)
    audit(request, "inventory.level_settings", f"{data.sku}@{data.branch}",
          f"โควตาออนไลน์ {data.online_quota if data.online_quota is not None else 'ไม่จำกัด'}, "
          f"จุดเตือน {data.low_stock_threshold if data.low_stock_threshold is not None else 'ค่ากลาง'}")
    return _level_out(data.branch, lv, _sold_today([lv.id]).get(lv.id, 0))


@router.post("/sold-out", response=LevelOut, auth=requires("inventory.adjust"))
def sold_out(request, data: SoldOutIn):
    """The counter sold the rest: stop online sales for this size at this branch now."""
    lv = services.sold_out_at_counter(branch=_branch(data.branch), variant=_variant(data.sku), note=data.note,
                                      actor=request.user.get_username())
    return _level_out(data.branch, lv, _sold_today([lv.id]).get(lv.id, 0))


@router.get("/import/template", response=TemplateOut, auth=requires("inventory.adjust"))
def import_template(request):
    return {"filename": "stock-template.csv", "csv": services.import_template()}


@router.post("/import/preview", response=ImportPreviewOut, auth=requires("inventory.adjust"))
def import_preview(request, data: ImportIn):
    """Check a stock file and show what would change. Nothing is written."""
    return services.parse_import(data.csv)


@router.post("/import/apply", response=ImportResultOut, auth=requires("inventory.adjust"))
def import_apply(request, data: ImportIn):
    result = services.apply_import(data.csv, actor=request.user.get_username())
    audit(request, "inventory.import", "stock csv", f"{result['rows']} แถว เปลี่ยน {result['changed']} รายการ")
    return result


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
