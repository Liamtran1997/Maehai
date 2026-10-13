"""Stock counts (CNT-) and end-of-day counter sales.

A count is a slip with one line per counted item at one place:
  1. start      the slip lists every tracked size and every active material at the place
  2. count      staff type what they found; the system records what was on hand at that moment
  3. submit     if the counted figures are still true (nothing moved since they were typed), the total
                difference decides: at most AUTO_APPROVE_UNITS units is posted at once, more waits for an approver
  4. approve    the difference becomes a 'count' movement; a rejected count goes back to counting with a reason

Blind counting: the counter does not need the expected figure, the API only shows it to approvers.
"""
from decimal import Decimal

from django.db import transaction
from django.db.models import F
from django.utils import timezone
from ninja.errors import HttpError

from maehai.catalog.models import ProductVariant

from . import documents
from .models import Branch, Document, DocumentLine, Material, MaterialLevel, MaterialMovement, StockLevel, StockMovement
from .services import refresh_low_alert

AUTO_APPROVE_UNITS = Decimal(20)   # a count whose total difference is at most this is posted without an approver


def _tracked_variants():
    return ProductVariant.objects.filter(is_active=True, product__is_active=True, track_stock=True).select_related("product")


def _on_hand(branch: Branch, line: DocumentLine) -> Decimal:
    if line.variant_id:
        lv = StockLevel.objects.filter(branch=branch, variant_id=line.variant_id).first()
        return Decimal(lv.on_hand) if lv else Decimal(0)
    ml = MaterialLevel.objects.filter(branch=branch, material_id=line.material_id).first()
    return ml.on_hand if ml else Decimal(0)


def _item_name(line: DocumentLine) -> str:
    return line.item_name


@transaction.atomic
def start_count(*, branch: Branch, actor: str, note: str = "") -> Document:
    doc = Document.objects.create(kind=Document.Kind.COUNT, status=Document.Status.COUNTING, to_branch=branch,
                                  note=note[:500], created_by=actor)
    documents._number(doc)
    for v in _tracked_variants():
        lv = StockLevel.objects.filter(branch=branch, variant=v).first()
        DocumentLine.objects.create(document=doc, variant=v, sent=Decimal(lv.on_hand) if lv else Decimal(0))
    for m in Material.objects.filter(is_active=True):
        ml = MaterialLevel.objects.filter(branch=branch, material=m).first()
        DocumentLine.objects.create(document=doc, material=m, sent=ml.on_hand if ml else Decimal(0))
    return doc


def _check_counting(doc: Document) -> None:
    if doc.kind != Document.Kind.COUNT:
        raise HttpError(422, "ใบนี้ไม่ใช่ใบนับสต็อก")
    if doc.status != Document.Status.COUNTING:
        raise HttpError(409, "ใบนี้ไม่ได้อยู่ในขั้นตอนนับ")


@transaction.atomic
def record_counts(doc: Document, *, entries) -> Document:
    """Save what the counter found. Each figure is stamped with what was on hand at that moment."""
    _check_counting(doc)
    lines = {ln.id: ln for ln in doc.lines.select_related("variant__product", "material")}
    for e in entries or []:
        try:
            lid = int(e.get("line_id"))
        except (TypeError, ValueError):
            raise HttpError(422, "รายการไม่ถูกต้อง")
        ln = lines.get(lid)
        if ln is None:
            raise HttpError(422, "ไม่พบรายการนี้ในใบนับ")
        raw = str(e.get("counted", "")).strip()
        try:
            value = Decimal(raw)
        except Exception:
            raise HttpError(422, f"{_item_name(ln)}: จำนวนไม่ถูกต้อง")
        if not value.is_finite() or value < 0 or value > Decimal(1_000_000):
            raise HttpError(422, f"{_item_name(ln)}: จำนวนต้องอยู่ระหว่าง 0 ถึง 1,000,000")
        if value.quantize(Decimal("0.001")) != value:
            raise HttpError(422, f"{_item_name(ln)}: ทศนิยมได้ไม่เกิน 3 ตำแหน่ง")
        if ln.variant_id and value != value.to_integral_value():
            raise HttpError(422, f"{_item_name(ln)}: สินค้าสำเร็จรูปต้องเป็นจำนวนเต็ม")
        ln.expected = _on_hand(doc.to_branch, ln)
        ln.counted = value.quantize(Decimal("0.001"))
        ln.counted_at = timezone.now()
        ln.save(update_fields=["expected", "counted", "counted_at"])
    return doc


def _moved_since(doc: Document, ln: DocumentLine) -> bool:
    if ln.counted_at is None:
        return False
    if ln.variant_id:
        return StockMovement.objects.filter(branch=doc.to_branch, variant_id=ln.variant_id, created_at__gt=ln.counted_at).exists()
    return MaterialMovement.objects.filter(branch=doc.to_branch, material_id=ln.material_id, created_at__gt=ln.counted_at).exists()


def variance(ln: DocumentLine) -> Decimal:
    return Decimal(ln.counted or 0) - Decimal(ln.expected or 0)


@transaction.atomic
def submit_count(doc: Document, *, actor: str, can_approve: bool) -> Document:
    _check_counting(doc)
    lines = list(doc.lines.select_related("variant__product", "material"))
    missing = [_item_name(ln) for ln in lines if ln.counted is None]
    if missing:
        raise HttpError(422, f"ยังนับไม่ครบ {len(missing)} รายการ เช่น {missing[0]}")
    stale = [_item_name(ln) for ln in lines if _moved_since(doc, ln)]
    if stale:
        raise HttpError(409, f"สต็อกเปลี่ยนหลังนับ ต้องนับใหม่: {', '.join(stale[:5])}")
    total = sum((abs(variance(ln)) for ln in lines), Decimal(0))
    if total <= AUTO_APPROVE_UNITS:
        return _post(doc, actor=actor)
    doc.status = Document.Status.PENDING_APPROVAL
    doc.save(update_fields=["status"])
    return doc


@transaction.atomic
def approve_count(doc: Document, *, actor: str) -> Document:
    if doc.kind != Document.Kind.COUNT or doc.status != Document.Status.PENDING_APPROVAL:
        raise HttpError(409, "ใบนี้ไม่รอการอนุมัติ")
    return _post(doc, actor=actor)


@transaction.atomic
def reject_count(doc: Document, *, actor: str, reason: str) -> Document:
    if doc.kind != Document.Kind.COUNT or doc.status != Document.Status.PENDING_APPROVAL:
        raise HttpError(409, "ใบนี้ไม่รอการอนุมัติ")
    reason = reason.strip()
    if not reason:
        raise HttpError(422, "ต้องระบุเหตุผลที่ส่งกลับไปนับใหม่")
    doc.status = Document.Status.COUNTING
    doc.review_note = reason[:300]
    doc.save(update_fields=["status", "review_note"])
    return doc


@transaction.atomic
def cancel_count(doc: Document, *, actor: str) -> Document:
    _check_counting(doc)
    doc.status = Document.Status.CANCELLED
    doc.closed_by, doc.closed_at = actor, timezone.now()
    doc.save(update_fields=["status", "closed_by", "closed_at"])
    return doc


def _post(doc: Document, *, actor: str) -> Document:
    """Write each difference into the ledger. Refuses if any item would drop below what orders already hold."""
    branch = doc.to_branch
    for ln in doc.lines.select_related("variant__product", "material"):
        diff = variance(ln)
        if diff == 0:
            continue
        if ln.variant_id:
            lv, _ = StockLevel.objects.get_or_create(branch=branch, variant_id=ln.variant_id)
            lv = StockLevel.objects.select_for_update().get(pk=lv.pk)
            new = lv.on_hand + int(diff)
            if new < lv.reserved:
                raise HttpError(409, f"{_item_name(ln)}: ของที่นับได้น้อยกว่าที่จองไว้ ({lv.reserved})")
            lv.on_hand = new
            lv.save(update_fields=["on_hand"])
            StockMovement.objects.create(branch=branch, variant_id=ln.variant_id, delta=int(diff), on_hand_after=new,
                                         reason=StockMovement.Reason.COUNT, document=doc, actor=actor, note=doc.number)
            refresh_low_alert(branch, ln.variant, decreased=diff < 0)
        else:
            ml, _ = MaterialLevel.objects.get_or_create(branch=branch, material_id=ln.material_id)
            ml = MaterialLevel.objects.select_for_update().get(pk=ml.pk)
            new = ml.on_hand + diff
            if new < 0:
                raise HttpError(409, f"{_item_name(ln)}: ของที่นับได้ติดลบ")
            ml.on_hand = new
            ml.save(update_fields=["on_hand"])
            MaterialMovement.objects.create(branch=branch, material_id=ln.material_id, delta=diff, on_hand_after=new,
                                            reason=MaterialMovement.Reason.COUNT, document=doc, actor=actor, note=doc.number)
    doc.status = Document.Status.POSTED
    doc.closed_by, doc.closed_at = actor, timezone.now()
    doc.save(update_fields=["status", "closed_by", "closed_at"])
    return doc


@transaction.atomic
def day_close(*, branch: Branch, sales: list[dict], actor: str, note: str = "") -> dict:
    """End of day at the counter: take the sizes sold over the counter off the shelf (reason counter_sale).
    Online orders already promised stay put: only what is free can be sold at the counter."""
    done = []
    for row in sales:
        sku = (row.get("sku") or "").strip()
        try:
            qty = int(row.get("sold"))
        except (TypeError, ValueError):
            raise HttpError(422, "จำนวนที่ขายไม่ถูกต้อง")
        if qty <= 0:
            continue
        v = ProductVariant.objects.select_related("product").filter(sku=sku).first()
        if v is None or not v.track_stock:
            raise HttpError(422, f"{sku} ไม่ได้เปิดนับสต็อก")
        documents._take(branch, {"kind": "variant", "obj": v, "qty": Decimal(qty), "cost": None}, Decimal(qty),
                        StockMovement.Reason.COUNTER_SALE, None, actor)
        done.append({"sku": sku, "sold": qty})
    return {"branch": branch.code, "lines": done}
