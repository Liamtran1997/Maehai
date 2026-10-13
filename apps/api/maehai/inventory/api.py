"""Staff-only stock management: branches, stock levels, materials, sources and warehouse documents.

Every endpoint names the permission it needs (requires). On top of that, a person only sees and acts on the
branches assigned to them (visible_branch_ids). Owners and managers see every branch.
"""
from decimal import Decimal

from django.shortcuts import get_object_or_404
from django.utils import timezone
from ninja import Field, Router, Schema
from ninja.errors import HttpError

from maehai.catalog.models import ProductVariant
from maehai.core.auth import requires
from maehai.core.models import audit
from maehai.core.permissions import ALL_BRANCH_ROLES, has, role_of, visible_branch_ids

from . import counts, documents, reconcile, services
from .models import Branch, Document, DocumentLine, Material, MaterialLevel, MaterialMovement, OnlineSale, Source, StockLevel, StockMovement

router = Router(tags=["admin-inventory"])


# ---------------------------------------------------------------- schemas

class StockBranchOut(Schema):
    code: str
    name: str
    kind: str


class LevelOut(Schema):
    branch: str
    on_hand: int
    reserved: int
    available: int
    online_quota: int | None = None
    online_sold_today: int = 0
    online_available: int = 0
    low_stock_threshold: int | None = None
    low_stock_line: int = 0


class StockRowOut(Schema):
    sku: str
    product_name: str
    variant_label: str
    track_stock: bool
    levels: list[LevelOut]


class AdjustIn(Schema):
    branch: str
    sku: str
    reason: str                     # waste | count
    quantity: int = Field(ge=0, le=1_000_000)
    note: str = Field(default="", max_length=200)


class PlaceSettingsOut(Schema):
    code: str
    name: str
    kind: str
    line_group_id: str


class LineGroupIn(Schema):
    line_group_id: str = Field(default="", max_length=64, pattern=r"^[A-Za-z0-9]*$")


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
    document_number: str | None
    actor: str


class MaterialIn(Schema):
    code: str = Field(min_length=2, max_length=60, pattern=r"^[a-z0-9][a-z0-9-]*$")
    name: str = Field(min_length=1, max_length=120)
    kind: str                       # material | supply | other
    unit: str = Field(min_length=1, max_length=20)
    low_stock_threshold: Decimal | None = None
    note: str = Field(default="", max_length=200)


class MaterialUpdate(Schema):
    name: str = Field(min_length=1, max_length=120)
    kind: str
    low_stock_threshold: Decimal | None = None
    note: str = Field(default="", max_length=200)
    is_active: bool = True


class MaterialOut(Schema):
    code: str
    name: str
    kind: str
    kind_label: str
    unit: str
    low_stock_threshold: str | None
    note: str
    is_active: bool
    in_use: bool


class MaterialAdjustIn(Schema):
    branch: str
    material_code: str
    reason: str                     # waste | consume | count
    quantity: Decimal
    note: str = Field(default="", max_length=200)


class MaterialLevelOut(Schema):
    branch: str
    on_hand: str
    low: bool


class MaterialStockOut(Schema):
    code: str
    name: str
    kind: str
    unit: str
    low_stock_threshold: str | None
    levels: list[MaterialLevelOut]


class SourceIn(Schema):
    name: str = Field(min_length=1, max_length=100)
    kind: str
    phone: str = Field(default="", max_length=30)
    note: str = Field(default="", max_length=200)
    is_active: bool = True


class SourceOut(Schema):
    id: int
    name: str
    kind: str
    kind_label: str
    phone: str
    note: str
    is_active: bool


class LineIn(Schema):
    sku: str | None = None
    material_code: str | None = None
    quantity: Decimal
    unit_cost_satang: int | None = Field(default=None, ge=0)


class ReceiptIn(Schema):
    source_id: int
    supplier_ref: str = Field(default="", max_length=60)
    note: str = Field(default="", max_length=500)
    lines: list[LineIn]


class TransferIn(Schema):
    to_branch: str
    vehicle: str = Field(min_length=1, max_length=100)
    carrier: str = Field(default="", max_length=100)
    note: str = Field(default="", max_length=500)
    lines: list[LineIn]


class CancelIn(Schema):
    reason: str = Field(min_length=1, max_length=300)


class ReceiveLineIn(Schema):
    line_id: int
    received: Decimal
    reason: str = ""                # damaged | wrong | other | missing (only when something is short)
    note: str = Field(default="", max_length=300)


class ReceiveTransferIn(Schema):
    lines: list[ReceiveLineIn]
    substitute_reason: str = Field(default="", max_length=300)


class StoreReturnIn(Schema):
    branch: str
    note: str = Field(default="", max_length=500)
    lines: list[LineIn]


class ReturnLineIn(Schema):
    line_id: int
    restock: Decimal = Decimal(0)
    discard: Decimal = Decimal(0)


class ReceiveReturnIn(Schema):
    lines: list[ReturnLineIn]


class CountEntryIn(Schema):
    line_id: int
    counted: str = Field(max_length=20)


class RecordCountsIn(Schema):
    lines: list[CountEntryIn]


class CountStartIn(Schema):
    branch: str
    note: str = Field(default="", max_length=500)


class ReasonIn(Schema):
    reason: str = Field(min_length=1, max_length=300)


class SalesLineIn(Schema):
    sku: str
    sold: int = Field(ge=0, le=1_000_000)


class DayCloseIn(Schema):
    branch: str
    lines: list[SalesLineIn]


class DocLineOut(Schema):
    id: int
    item_kind: str
    sku: str | None
    material_code: str | None
    name: str
    unit: str
    sent: str
    received: str | None
    refused: str
    missing: str
    restocked: str
    discarded: str
    refuse_reason: str
    refuse_note: str
    unit_cost_satang: int | None
    expected: str | None = None
    counted: str | None = None
    variance: str | None = None


class DocOut(Schema):
    number: str
    kind: str
    kind_label: str
    status: str
    status_label: str
    from_branch: str | None
    to_branch: str | None
    source: str | None
    origin: str | None
    supplier_ref: str
    vehicle: str
    carrier: str
    note: str
    cancel_reason: str
    review_note: str
    created_by: str
    created_at: str
    sent_at: str | None
    closed_by: str
    closed_at: str | None
    substitute_reason: str
    line_count: int
    overdue: bool


class DocDetailOut(DocOut):
    lines: list[DocLineOut]


class ReconcileRowOut(Schema):
    kind: str
    id: int
    name: str
    unit: str
    opening: str
    flows: dict[str, str]
    closing: str
    on_hand: str
    balanced: bool
    in_transit_out: str
    in_transit_in: str
    lost: str
    discarded: str
    refused: str


class ReconcileOut(Schema):
    branch: str
    date_from: str
    date_to: str
    rows: list[ReconcileRowOut]
    unbalanced: int


# ---------------------------------------------------------------- helpers

def _visible(request) -> set[int] | None:
    return visible_branch_ids(request.user)


def _check_branch(request, branch: Branch) -> None:
    ids = _visible(request)
    if ids is not None and branch.id not in ids:
        raise HttpError(403, "ไม่มีสิทธิ์ทำรายการที่สาขานี้")


def _allowed_codes(request) -> set[str] | None:
    ids = _visible(request)
    if ids is None:
        return None
    return set(Branch.objects.filter(pk__in=ids).values_list("code", flat=True))


def _branch(code: str) -> Branch:
    return get_object_or_404(Branch, code=code, is_active=True)


def _variant(sku: str) -> ProductVariant:
    return get_object_or_404(ProductVariant.objects.select_related("product"), sku=sku)


def _level_out(code: str, lv: StockLevel | None, sold: int = 0) -> dict:
    if lv is None:
        return {"branch": code, "on_hand": 0, "reserved": 0, "available": 0, "online_quota": None, "online_sold_today": 0,
                "online_available": 0, "low_stock_threshold": None, "low_stock_line": StockLevel(low_stock_threshold=None).threshold}
    return {"branch": code, "on_hand": lv.on_hand, "reserved": lv.reserved, "available": lv.available,
            "online_quota": lv.online_quota, "online_sold_today": sold, "online_available": lv.online_available(sold),
            "low_stock_threshold": lv.low_stock_threshold, "low_stock_line": lv.threshold}


def _sold_today(level_ids) -> dict[int, int]:
    return dict(OnlineSale.objects.filter(level_id__in=level_ids, day=timezone.localdate()).values_list("level_id", "units"))


def _is_manager(request) -> bool:
    return role_of(request.user) in ALL_BRANCH_ROLES


def _doc_out(doc: Document) -> dict:
    return {
        "number": doc.number, "kind": doc.kind, "kind_label": doc.get_kind_display(), "status": doc.status,
        "status_label": doc.get_status_display(),
        "from_branch": doc.from_branch.code if doc.from_branch_id else None,
        "to_branch": doc.to_branch.code if doc.to_branch_id else None,
        "source": doc.source.name if doc.source_id else None,
        "origin": doc.origin.number if doc.origin_id else None,
        "supplier_ref": doc.supplier_ref, "vehicle": doc.vehicle, "carrier": doc.carrier, "note": doc.note,
        "cancel_reason": doc.cancel_reason, "review_note": doc.review_note, "created_by": doc.created_by,
        "created_at": doc.created_at.isoformat(), "sent_at": doc.sent_at.isoformat() if doc.sent_at else None,
        "closed_by": doc.closed_by, "closed_at": doc.closed_at.isoformat() if doc.closed_at else None,
        "substitute_reason": doc.substitute_reason, "line_count": doc.lines.count(),
        "overdue": doc.status in (Document.Status.SENT, Document.Status.SENT_BACK) and doc.sent_at is not None
        and (timezone.now() - doc.sent_at).total_seconds() > 24 * 3600,
    }


def _line_out(ln: DocumentLine, show_expected: bool = False) -> dict:
    v, m = ln.variant, ln.material
    var = counts.variance(ln) if ln.counted is not None else None
    return {
        "expected": str(ln.expected) if show_expected and ln.expected is not None else None,
        "counted": str(ln.counted) if ln.counted is not None else None,
        "variance": str(var) if show_expected and var is not None else None,
        "id": ln.id, "item_kind": "product" if v else "material",
        "sku": v.sku if v else None, "material_code": m.code if m else None,
        "name": (f"{v.product.name} ({v.label})" if v else m.name), "unit": "ชิ้น" if v else m.unit,
        "sent": str(ln.sent), "received": str(ln.received) if ln.received is not None else None,
        "refused": str(ln.refused), "missing": str(ln.missing), "restocked": str(ln.restocked),
        "discarded": str(ln.discarded), "refuse_reason": ln.refuse_reason, "refuse_note": ln.refuse_note,
        "unit_cost_satang": ln.unit_cost_satang,
    }


def _is_approver(request) -> bool:
    return has(request.user, "inventory.approve")


def _doc_detail(doc: Document, show_expected: bool = False) -> dict:
    lines = doc.lines.select_related("variant__product", "material").order_by("id")
    return {**_doc_out(doc), "lines": [_line_out(ln, show_expected) for ln in lines]}


def _visible_doc(request, number: str) -> Document:
    doc = get_object_or_404(Document.objects.select_related("from_branch", "to_branch", "source", "origin"), number=number)
    ids = _visible(request)
    if ids is not None and not ({doc.from_branch_id, doc.to_branch_id} & ids):
        raise HttpError(404, "ไม่พบเอกสารนี้")
    return doc


def _lines_in(lines) -> list[dict]:
    return [{"sku": ln.sku, "material_code": ln.material_code, "quantity": ln.quantity,
             "unit_cost_satang": ln.unit_cost_satang} for ln in lines]


# ---------------------------------------------------------------- branches and stock

@router.get("/branches", response=list[StockBranchOut], auth=requires("inventory.view"))
def branches(request):
    ids = _visible(request)
    qs = Branch.objects.filter(is_active=True)
    if ids is not None:
        qs = qs.filter(pk__in=ids)
    return qs


@router.get("/branches/settings", response=list[PlaceSettingsOut], auth=requires("inventory.approve"))
def branch_settings(request):
    return Branch.objects.filter(is_active=True)


@router.put("/branches/{code}/line-group", response=PlaceSettingsOut, auth=requires("inventory.approve"))
def set_line_group(request, code: str, data: LineGroupIn):
    """LINE group that gets this place's warehouse alerts. Empty = the shared staff group."""
    b = _branch(code)
    b.line_group_id = data.line_group_id.strip()
    b.save(update_fields=["line_group_id"])
    audit(request, "inventory.line_group", b.code, f"กลุ่ม LINE {'ตั้งค่าแล้ว' if b.line_group_id else 'ล้างแล้ว (ใช้กลุ่มกลาง)'}")
    return b


@router.get("/stock", response=list[StockRowOut], auth=requires("inventory.view"))
def stock(request, q: str | None = None, tracked_only: bool = False):
    qs = ProductVariant.objects.filter(is_active=True, product__is_active=True).select_related("product").prefetch_related("stock_levels__branch")
    if q:
        qs = qs.filter(product__name__icontains=q)
    if tracked_only:
        qs = qs.filter(track_stock=True)
    visible = _allowed_codes(request)
    order = [c for c in Branch.objects.filter(is_active=True).values_list("code", flat=True) if visible is None or c in visible]
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
    branch = _branch(data.branch)
    _check_branch(request, branch)
    lv = services.adjust(branch=branch, variant=_variant(data.sku), reason=data.reason,
                         quantity=data.quantity, note=data.note, actor=request.user.get_username())
    return _level_out(data.branch, lv, _sold_today([lv.id]).get(lv.id, 0))


@router.put("/levels", response=LevelOut, auth=requires("inventory.adjust"))
def level_settings(request, data: LevelSettingsIn):
    """Daily online quota and own low-stock line for one size at one branch."""
    branch = _branch(data.branch)
    _check_branch(request, branch)
    v = _variant(data.sku)
    lv = services.set_level_settings(branch=branch, variant=v, online_quota=data.online_quota,
                                     low_stock_threshold=data.low_stock_threshold)
    audit(request, "inventory.level_settings", f"{data.sku}@{data.branch}",
          f"โควตาออนไลน์ {data.online_quota if data.online_quota is not None else 'ไม่จำกัด'}, "
          f"จุดเตือน {data.low_stock_threshold if data.low_stock_threshold is not None else 'ค่ากลาง'}")
    return _level_out(data.branch, lv, _sold_today([lv.id]).get(lv.id, 0))


@router.post("/sold-out", response=LevelOut, auth=requires("inventory.adjust"))
def sold_out(request, data: SoldOutIn):
    """The counter sold the rest: stop online sales for this size at this branch now."""
    branch = _branch(data.branch)
    _check_branch(request, branch)
    lv = services.sold_out_at_counter(branch=branch, variant=_variant(data.sku), note=data.note,
                                      actor=request.user.get_username())
    return _level_out(data.branch, lv, _sold_today([lv.id]).get(lv.id, 0))


@router.get("/import/template", response=TemplateOut, auth=requires("inventory.adjust"))
def import_template(request):
    return {"filename": "stock-template.csv", "csv": services.import_template(_allowed_codes(request))}


@router.post("/import/preview", response=ImportPreviewOut, auth=requires("inventory.adjust"))
def import_preview(request, data: ImportIn):
    """Check a stock file and show what would change. Nothing is written."""
    return services.parse_import(data.csv, _allowed_codes(request))


@router.post("/import/apply", response=ImportResultOut, auth=requires("inventory.adjust"))
def import_apply(request, data: ImportIn):
    result = services.apply_import(data.csv, actor=request.user.get_username(), allowed_branch_codes=_allowed_codes(request))
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
    qs = StockMovement.objects.select_related("branch", "variant__product", "order", "document")
    ids = _visible(request)
    if ids is not None:
        qs = qs.filter(branch_id__in=ids)
    if sku:
        qs = qs.filter(variant__sku=sku)
    if branch:
        qs = qs.filter(branch__code=branch)
    return [{
        "created_at": m.created_at.isoformat(), "branch": m.branch.code, "sku": m.variant.sku,
        "product_name": m.variant.product.name, "variant_label": m.variant.label, "delta": m.delta,
        "on_hand_after": m.on_hand_after, "reason": m.reason, "reason_label": m.get_reason_display(), "note": m.note,
        "order_number": m.order.number if m.order else None,
        "document_number": m.document.number if m.document_id else None, "actor": m.actor,
    } for m in qs[:limit]]


# ---------------------------------------------------------------- materials

@router.get("/materials", response=list[MaterialOut], auth=requires("inventory.view"))
def materials(request, include_inactive: bool = False):
    qs = Material.objects.all()
    if not include_inactive:
        qs = qs.filter(is_active=True)
    used = set(MaterialMovement.objects.values_list("material_id", flat=True).distinct())
    return [{"code": m.code, "name": m.name, "kind": m.kind, "kind_label": m.get_kind_display(), "unit": m.unit,
             "low_stock_threshold": str(m.low_stock_threshold) if m.low_stock_threshold is not None else None,
             "note": m.note, "is_active": m.is_active, "in_use": m.id in used} for m in qs]


@router.post("/materials", response={201: MaterialOut}, auth=requires("inventory.receive"))
def create_material(request, data: MaterialIn):
    if data.kind not in Material.Kind.values:
        raise HttpError(422, "ประเภทไม่ถูกต้อง")
    if Material.objects.filter(code=data.code).exists():
        raise HttpError(409, "รหัสนี้มีอยู่แล้ว")
    if ProductVariant.objects.filter(sku=data.code).exists():
        raise HttpError(409, "รหัสนี้ซ้ำกับ SKU ของสินค้า")
    m = Material.objects.create(code=data.code, name=data.name.strip(), kind=data.kind, unit=data.unit.strip(),
                                low_stock_threshold=data.low_stock_threshold, note=data.note)
    audit(request, "inventory.material_create", m.code, f"{m.name} ({m.unit})")
    return 201, {"code": m.code, "name": m.name, "kind": m.kind, "kind_label": m.get_kind_display(), "unit": m.unit,
                 "low_stock_threshold": str(m.low_stock_threshold) if m.low_stock_threshold is not None else None,
                 "note": m.note, "is_active": m.is_active, "in_use": False}


@router.get("/materials/stock", response=list[MaterialStockOut], auth=requires("inventory.view"))
def materials_stock(request):
    visible = _allowed_codes(request)
    levels = {(ml.material_id, ml.branch.code): ml for ml in MaterialLevel.objects.select_related("branch")}
    rows = []
    for m in Material.objects.filter(is_active=True):
        cells = []
        for b in Branch.objects.filter(is_active=True):
            if visible is not None and b.code not in visible:
                continue
            ml = levels.get((m.id, b.code))
            on = ml.on_hand if ml else Decimal(0)
            low = m.low_stock_threshold is not None and on <= m.low_stock_threshold
            cells.append({"branch": b.code, "on_hand": str(on), "low": low})
        rows.append({"code": m.code, "name": m.name, "kind": m.kind, "unit": m.unit,
                     "low_stock_threshold": str(m.low_stock_threshold) if m.low_stock_threshold is not None else None,
                     "levels": cells})
    return rows


@router.post("/materials/adjust", response=MaterialStockOut, auth=requires("inventory.adjust"))
def adjust_material(request, data: MaterialAdjustIn):
    branch = _branch(data.branch)
    _check_branch(request, branch)
    m = get_object_or_404(Material, code=data.material_code, is_active=True)
    services.adjust_material(branch=branch, material=m, reason=data.reason, quantity=data.quantity,
                             actor=request.user.get_username(), note=data.note)
    on = MaterialLevel.objects.filter(branch=branch, material=m).values_list("on_hand", flat=True).first() or Decimal(0)
    return {"code": m.code, "name": m.name, "kind": m.kind, "unit": m.unit,
            "low_stock_threshold": str(m.low_stock_threshold) if m.low_stock_threshold is not None else None,
            "levels": [{"branch": branch.code, "on_hand": str(on), "low": m.low_stock_threshold is not None and on <= m.low_stock_threshold}]}


@router.put("/materials/{code}", response=MaterialOut, auth=requires("inventory.receive"))
def update_material(request, code: str, data: MaterialUpdate):
    m = get_object_or_404(Material, code=code)
    if data.kind not in Material.Kind.values:
        raise HttpError(422, "ประเภทไม่ถูกต้อง")
    m.name, m.kind, m.note = data.name.strip(), data.kind, data.note
    m.low_stock_threshold, m.is_active = data.low_stock_threshold, data.is_active
    m.save()
    used = MaterialMovement.objects.filter(material=m).exists()
    return {"code": m.code, "name": m.name, "kind": m.kind, "kind_label": m.get_kind_display(), "unit": m.unit,
            "low_stock_threshold": str(m.low_stock_threshold) if m.low_stock_threshold is not None else None,
            "note": m.note, "is_active": m.is_active, "in_use": used}


# ---------------------------------------------------------------- sources

def _source_out(s: Source) -> dict:
    return {"id": s.id, "name": s.name, "kind": s.kind, "kind_label": s.get_kind_display(), "phone": s.phone,
            "note": s.note, "is_active": s.is_active}


@router.get("/sources", response=list[SourceOut], auth=requires("inventory.receive"))
def sources(request, include_hidden: bool = False):
    qs = Source.objects.all() if include_hidden else Source.objects.filter(is_active=True)
    return [_source_out(s) for s in qs]


@router.post("/sources", response={201: SourceOut}, auth=requires("inventory.receive"))
def create_source(request, data: SourceIn):
    if data.kind not in Source.Kind.values:
        raise HttpError(422, "ประเภทไม่ถูกต้อง")
    s = Source.objects.create(name=data.name.strip(), kind=data.kind, phone=data.phone.strip(), note=data.note, is_active=data.is_active)
    return 201, _source_out(s)


@router.put("/sources/{source_id}", response=SourceOut, auth=requires("inventory.receive"))
def update_source(request, source_id: int, data: SourceIn):
    s = get_object_or_404(Source, pk=source_id)
    if data.kind not in Source.Kind.values:
        raise HttpError(422, "ประเภทไม่ถูกต้อง")
    s.name, s.kind, s.phone, s.note, s.is_active = data.name.strip(), data.kind, data.phone.strip(), data.note, data.is_active
    s.save()
    return _source_out(s)


# ---------------------------------------------------------------- documents

@router.get("/documents", response=list[DocOut], auth=requires("inventory.view"))
def list_documents(request, kind: str | None = None, status: str | None = None, branch: str | None = None, limit: int = 50):
    limit = max(1, min(limit, 200))
    qs = Document.objects.select_related("from_branch", "to_branch", "source", "origin")
    ids = _visible(request)
    if ids is not None:
        qs = qs.filter(from_branch_id__in=ids) | qs.filter(to_branch_id__in=ids)
    if kind:
        qs = qs.filter(kind=kind)
    if status:
        qs = qs.filter(status=status)
    if branch:
        qs = qs.filter(from_branch__code=branch) | qs.filter(to_branch__code=branch)
    return [_doc_out(d) for d in qs.distinct()[:limit]]


@router.post("/documents/receipts", response={201: DocDetailOut}, auth=requires("inventory.receive"))
def create_receipt(request, data: ReceiptIn):
    source = get_object_or_404(Source, pk=data.source_id)
    _check_branch(request, documents.central_branch())
    doc = documents.create_receipt(source=source, supplier_ref=data.supplier_ref, note=data.note,
                                   lines=_lines_in(data.lines), actor=request.user.get_username())
    return 201, _doc_detail(doc)


@router.post("/documents/transfers", response={201: DocDetailOut}, auth=requires("inventory.transfer"))
def create_transfer(request, data: TransferIn):
    central = documents.central_branch()
    _check_branch(request, central)
    to = _branch(data.to_branch)
    doc = documents.create_transfer(to_branch=to, vehicle=data.vehicle, carrier=data.carrier, note=data.note,
                                    lines=_lines_in(data.lines), actor=request.user.get_username())
    return 201, _doc_detail(doc)


@router.post("/documents/{number}/cancel", response=DocDetailOut, auth=requires("inventory.transfer"))
def cancel_transfer(request, number: str, data: CancelIn):
    doc = _visible_doc(request, number)
    doc = documents.cancel_transfer(doc, actor=request.user.get_username(), reason=data.reason, is_manager=_is_manager(request))
    return _doc_detail(doc)


@router.post("/documents/{number}/receive", response=DocDetailOut, auth=requires("inventory.receive_transfer"))
def receive_transfer(request, number: str, data: ReceiveTransferIn):
    doc = _visible_doc(request, number)
    if doc.kind == Document.Kind.TRANSFER:
        _check_branch(request, doc.to_branch)
    substitute = role_of(request.user) != "branch_manager"
    if substitute and not data.substitute_reason.strip():
        raise HttpError(422, "ผู้ที่ไม่ใช่ผู้จัดการสาขานี้ต้องระบุเหตุผลที่รับแทน")
    lines = [{"line_id": ln.line_id, "received": str(ln.received), "reason": ln.reason, "note": ln.note} for ln in data.lines]
    doc = documents.receive_transfer(doc, actor=request.user.get_username(), lines=lines,
                                     substitute_reason=data.substitute_reason if substitute else "")
    return _doc_detail(doc)


@router.post("/documents/returns", response={201: DocDetailOut}, auth=requires("inventory.adjust"))
def create_store_return(request, data: StoreReturnIn):
    branch = _branch(data.branch)
    _check_branch(request, branch)
    doc = documents.create_store_return(branch=branch, note=data.note, lines=_lines_in(data.lines),
                                        actor=request.user.get_username())
    return 201, _doc_detail(doc)


@router.post("/documents/{number}/receive-return", response=DocDetailOut, auth=requires("inventory.receive_return"))
def receive_return(request, number: str, data: ReceiveReturnIn):
    doc = _visible_doc(request, number)
    _check_branch(request, doc.to_branch)
    lines = [{"line_id": ln.line_id, "restock": str(ln.restock), "discard": str(ln.discard)} for ln in data.lines]
    doc = documents.receive_return(doc, actor=request.user.get_username(), lines=lines)
    return _doc_detail(doc)


@router.get("/documents/{number}", response=DocDetailOut, auth=requires("inventory.view"))
def get_document(request, number: str):
    return _doc_detail(_visible_doc(request, number), show_expected=_is_approver(request))


# ---------------------------------------------------------------- stock counts and counter sales

@router.post("/counts", response={201: DocDetailOut}, auth=requires("inventory.adjust"))
def start_count(request, data: CountStartIn):
    branch = _branch(data.branch)
    _check_branch(request, branch)
    doc = counts.start_count(branch=branch, actor=request.user.get_username(), note=data.note)
    return 201, _doc_detail(doc)


@router.put("/counts/{number}/lines", response=DocDetailOut, auth=requires("inventory.adjust"))
def record_counts(request, number: str, data: RecordCountsIn):
    doc = _visible_doc(request, number)
    _check_branch(request, doc.to_branch)
    doc = counts.record_counts(doc, entries=[{"line_id": e.line_id, "counted": e.counted} for e in data.lines])
    return _doc_detail(doc, show_expected=_is_approver(request))


@router.post("/counts/{number}/submit", response=DocDetailOut, auth=requires("inventory.adjust"))
def submit_count(request, number: str):
    doc = _visible_doc(request, number)
    _check_branch(request, doc.to_branch)
    doc = counts.submit_count(doc, actor=request.user.get_username(), can_approve=_is_approver(request))
    return _doc_detail(doc, show_expected=_is_approver(request))


@router.post("/counts/{number}/approve", response=DocDetailOut, auth=requires("inventory.approve"))
def approve_count(request, number: str):
    doc = _visible_doc(request, number)
    doc = counts.approve_count(doc, actor=request.user.get_username())
    audit(request, "inventory.count_approve", doc.number, f"ปรับสต็อกตามใบนับ ({doc.to_branch.name})")
    return _doc_detail(doc, show_expected=True)


@router.post("/counts/{number}/reject", response=DocDetailOut, auth=requires("inventory.approve"))
def reject_count(request, number: str, data: ReasonIn):
    doc = _visible_doc(request, number)
    doc = counts.reject_count(doc, actor=request.user.get_username(), reason=data.reason)
    audit(request, "inventory.count_reject", doc.number, data.reason)
    return _doc_detail(doc, show_expected=True)


@router.post("/counts/{number}/cancel", response=DocDetailOut, auth=requires("inventory.adjust"))
def cancel_count(request, number: str):
    doc = _visible_doc(request, number)
    _check_branch(request, doc.to_branch)
    return _doc_detail(counts.cancel_count(doc, actor=request.user.get_username()))


@router.post("/branches/{code}/day-close", auth=requires("inventory.adjust"))
def day_close(request, code: str, data: DayCloseIn):
    """Counter sales for the day, taken off the shelf at this branch."""
    branch = _branch(code)
    _check_branch(request, branch)
    result = counts.day_close(branch=branch, sales=[{"sku": ln.sku, "sold": ln.sold} for ln in data.lines],
                              actor=request.user.get_username())
    audit(request, "inventory.day_close", branch.code, f"ขายหน้าร้าน {len(result['lines'])} รายการ")
    return result


# ---------------------------------------------------------------- reports

@router.get("/reports/reconcile", response=ReconcileOut, auth=requires("inventory.view"))
def reconcile_report(request, branch: str, date_from: str, date_to: str):
    import datetime as dt

    b = _branch(branch)
    _check_branch(request, b)
    try:
        d1, d2 = dt.date.fromisoformat(date_from), dt.date.fromisoformat(date_to)
    except ValueError:
        raise HttpError(422, "วันที่ไม่ถูกต้อง")
    if d2 < d1 or (d2 - d1).days > 366:
        raise HttpError(422, "ช่วงวันที่ต้องไม่เกิน 1 ปี และวันสิ้นสุดต้องไม่ก่อนวันเริ่ม")
    out = reconcile.reconcile(b, d1, d2)
    return {"branch": out["branch"], "date_from": out["from"], "date_to": out["to"], "rows": out["rows"], "unbalanced": out["unbalanced"]}
