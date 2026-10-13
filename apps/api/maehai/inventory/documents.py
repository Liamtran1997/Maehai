"""Warehouse documents: what goes into the central warehouse, what it sends to the branches, and what comes back.

Three slips (see Document):
  receipt   IN-  a source delivers to the central warehouse. Stock goes up at once.
  transfer  TR-  the central warehouse sends goods to one branch. Stock goes down at once, the goods are
                 "in transit" until the branch confirms what arrived. Refused goods become a return slip.
  return    RT-  goods coming back to the central warehouse: refused on a transfer, or sent back by a branch.

Rules that hold everywhere:
- A place's on_hand changes only when goods physically enter or leave it. Goods on a truck are in transit, not
  on any shelf, so they can neither be sold nor counted.
- Goods lost on the way (missing) and goods thrown away (discarded) never come back to on_hand. They are kept on
  the slip line, so the reconciliation report can show them.
- Every change runs in one transaction. Any refusal (not enough stock, wrong status) rolls the whole slip back.
"""
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone
from ninja.errors import HttpError

from maehai.catalog.models import ProductVariant
from maehai.notifications import events as notify

from . import services as stock
from .models import Branch, Document, DocumentLine, Material, MaterialLevel, MaterialMovement, Source, StockLevel, StockMovement

Q3 = Decimal("0.001")
MAX_QTY = Decimal("1000000")
MAX_LINES = 100
OVERDUE_AFTER = timedelta(hours=24)
REFUSE_REASONS = {"damaged": "ชำรุด", "wrong": "ไม่ตรงรายการ", "other": "อื่นๆ"}
LOST = "missing"                         # a receive-line reason: lost on the way, never comes back
PREFIX = {Document.Kind.RECEIPT: "IN", Document.Kind.TRANSFER: "TR", Document.Kind.RETURN: "RT"}


# ---------------------------------------------------------------- helpers

def central_branch() -> Branch:
    b = Branch.objects.filter(kind=Branch.Kind.CENTRAL, is_active=True).first()
    if b is None:
        raise HttpError(409, "ยังไม่ได้ตั้งสาขาคลังกลาง")
    return b


def _qty(value, *, integer: bool) -> Decimal:
    try:
        d = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        raise HttpError(422, "จำนวนไม่ถูกต้อง")
    if not d.is_finite() or d <= 0 or d > MAX_QTY:
        raise HttpError(422, "จำนวนต้องมากกว่า 0 และไม่เกิน 1,000,000")
    if d.quantize(Q3) != d:
        raise HttpError(422, "ทศนิยมได้ไม่เกิน 3 ตำแหน่ง")
    if integer and d != d.to_integral_value():
        raise HttpError(422, "สินค้าสำเร็จรูปต้องเป็นจำนวนเต็ม")
    return d.quantize(Q3)


def _received(value, *, sent: Decimal, integer: bool) -> Decimal:
    """What the receiving branch counted: 0 up to what was sent (zero is allowed: nothing arrived)."""
    try:
        d = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        raise HttpError(422, "จำนวนที่รับไม่ถูกต้อง")
    if not d.is_finite() or d < 0 or d > sent:
        raise HttpError(422, f"รับได้ตั้งแต่ 0 ถึง {sent:g}")
    if d.quantize(Q3) != d or (integer and d != d.to_integral_value()):
        raise HttpError(422, "จำนวนที่รับไม่ถูกต้อง")
    return d.quantize(Q3)


def _resolve_lines(lines) -> list[dict]:
    """Turn request lines into (variant or material, quantity). One item per line; no duplicates."""
    if not lines:
        raise HttpError(422, "ต้องมีรายการสินค้าอย่างน้อย 1 รายการ")
    if len(lines) > MAX_LINES:
        raise HttpError(422, f"มีได้ไม่เกิน {MAX_LINES} รายการต่อใบ")
    out, seen = [], set()
    for ln in lines:
        sku = (ln.get("sku") or "").strip()
        code = (ln.get("material_code") or "").strip()
        if bool(sku) == bool(code):
            raise HttpError(422, "แต่ละรายการต้องระบุ SKU หรือรหัสวัตถุดิบ อย่างใดอย่างหนึ่ง")
        if sku:
            v = ProductVariant.objects.select_related("product").filter(sku=sku, is_active=True, product__is_active=True).first()
            if v is None:
                raise HttpError(422, f"ไม่พบสินค้า SKU {sku}")
            if not v.track_stock:
                raise HttpError(409, f"{v.product.name} ({v.label}) ต้องเปิดนับสต็อกก่อน")
            item = ("variant", v)
            qty = _qty(ln.get("quantity"), integer=True)
        else:
            m = Material.objects.filter(code=code, is_active=True).first()
            if m is None:
                raise HttpError(422, f"ไม่พบรายการวัตถุดิบ {code}")
            item = ("material", m)
            qty = _qty(ln.get("quantity"), integer=False)
        key = (item[0], item[1].pk)
        if key in seen:
            raise HttpError(422, "รายการซ้ำในใบเดียวกัน กรุณารวมจำนวนเป็นบรรทัดเดียว")
        seen.add(key)
        cost = ln.get("unit_cost_satang")
        if cost is not None and cost < 0:
            raise HttpError(422, "ราคาต่อหน่วยต้องไม่ติดลบ")
        out.append({"kind": item[0], "obj": item[1], "qty": qty, "cost": cost})
    return out


def _is_product(item) -> bool:
    return item["kind"] == "variant"


def _line_kwargs(item) -> dict:
    return {"variant": item["obj"]} if _is_product(item) else {"material": item["obj"]}


def _item_name(item) -> str:
    o = item["obj"]
    return f"{o.product.name} ({o.label})" if _is_product(item) else o.name


def _number(doc: Document) -> None:
    be_year = timezone.localtime(doc.created_at).year + 543
    doc.number = f"{PREFIX[doc.kind]}-{be_year}-{doc.pk:06d}"
    doc.save(update_fields=["number"])


def _add(branch: Branch, item: dict, qty: Decimal, reason: str, doc: Document, actor: str) -> None:
    if _is_product(item):
        v = item["obj"]
        lv, _ = StockLevel.objects.get_or_create(branch=branch, variant=v)
        lv = StockLevel.objects.select_for_update().get(pk=lv.pk)
        lv.on_hand += int(qty)
        lv.save(update_fields=["on_hand"])
        StockMovement.objects.create(branch=branch, variant=v, delta=int(qty), on_hand_after=lv.on_hand, reason=reason,
                                     document=doc, actor=actor)
        stock.refresh_low_alert(branch, v, decreased=False)
        stock.notify_if_restocked(v)
    else:
        m = item["obj"]
        ml, _ = MaterialLevel.objects.get_or_create(branch=branch, material=m)
        ml = MaterialLevel.objects.select_for_update().get(pk=ml.pk)
        ml.on_hand += qty
        ml.save(update_fields=["on_hand"])
        MaterialMovement.objects.create(branch=branch, material=m, delta=qty, on_hand_after=ml.on_hand, reason=reason,
                                        document=doc, actor=actor)


def _take(branch: Branch, item: dict, qty: Decimal, reason: str, doc: Document, actor: str) -> None:
    """Take goods out of a place. Fails the whole slip if the place cannot give that much."""
    if _is_product(item):
        v = item["obj"]
        lv, _ = StockLevel.objects.get_or_create(branch=branch, variant=v)
        lv = StockLevel.objects.select_for_update().get(pk=lv.pk)
        # Units promised to online orders stay put: only what is free can leave.
        if lv.available < int(qty):
            raise HttpError(409, f"{_item_name(item)} ที่{branch.name}มีให้ส่งได้แค่ {max(lv.available, 0)}")
        lv.on_hand -= int(qty)
        lv.save(update_fields=["on_hand"])
        StockMovement.objects.create(branch=branch, variant=v, delta=-int(qty), on_hand_after=lv.on_hand, reason=reason,
                                     document=doc, actor=actor)
        stock.refresh_low_alert(branch, v, decreased=True)
    else:
        m = item["obj"]
        ml, _ = MaterialLevel.objects.get_or_create(branch=branch, material=m)
        ml = MaterialLevel.objects.select_for_update().get(pk=ml.pk)
        if ml.on_hand < qty:
            raise HttpError(409, f"{m.name} ที่{branch.name}มีแค่ {ml.on_hand:g} {m.unit}")
        ml.on_hand -= qty
        ml.save(update_fields=["on_hand"])
        MaterialMovement.objects.create(branch=branch, material=m, delta=-qty, on_hand_after=ml.on_hand, reason=reason,
                                        document=doc, actor=actor)


def _new_doc(**fields) -> Document:
    doc = Document.objects.create(**fields)
    _number(doc)
    return doc


# ---------------------------------------------------------------- receipts (IN-)

@transaction.atomic
def create_receipt(*, source: Source, supplier_ref: str, note: str, lines, actor: str) -> Document:
    if not source.is_active:
        raise HttpError(422, "แหล่งสินค้านี้ถูกซ่อนอยู่")
    central = central_branch()
    items = _resolve_lines(lines)
    doc = _new_doc(kind=Document.Kind.RECEIPT, status=Document.Status.POSTED, to_branch=central, source=source,
                   supplier_ref=supplier_ref.strip()[:60], note=note[:500], created_by=actor)
    for it in items:
        DocumentLine.objects.create(document=doc, sent=it["qty"], received=it["qty"],
                                    unit_cost_satang=it["cost"], **_line_kwargs(it))
        _add(central, it, it["qty"], StockMovement.Reason.RECEIVE if _is_product(it) else MaterialMovement.Reason.RECEIVE,
             doc, actor)
    return doc


# ---------------------------------------------------------------- transfers (TR-)

@transaction.atomic
def create_transfer(*, to_branch: Branch, vehicle: str, carrier: str, note: str, lines, actor: str) -> Document:
    central = central_branch()
    if to_branch.id == central.id or to_branch.kind != Branch.Kind.STORE or not to_branch.is_active:
        raise HttpError(422, "ปลายทางต้องเป็นสาขาที่ใช้งานอยู่ (ไม่ใช่คลังกลาง)")
    vehicle = vehicle.strip()
    if not vehicle:
        raise HttpError(422, "ต้องระบุรถที่ใช้ส่ง")
    items = _resolve_lines(lines)
    doc = _new_doc(kind=Document.Kind.TRANSFER, status=Document.Status.SENT, from_branch=central, to_branch=to_branch,
                   vehicle=vehicle[:100], carrier=carrier.strip()[:100], note=note[:500], created_by=actor,
                   sent_at=timezone.now())
    for it in items:
        DocumentLine.objects.create(document=doc, sent=it["qty"], **_line_kwargs(it))
        _take(central, it, it["qty"], StockMovement.Reason.TRANSFER_OUT if _is_product(it) else MaterialMovement.Reason.TRANSFER_OUT,
              doc, actor)
    notify.transfer_sent(doc)
    return doc


@transaction.atomic
def cancel_transfer(doc: Document, *, actor: str, reason: str, is_manager: bool) -> Document:
    if doc.kind != Document.Kind.TRANSFER:
        raise HttpError(422, "ใบนี้ไม่ใช่ใบส่งสินค้า")
    if doc.status != Document.Status.SENT:
        raise HttpError(409, "ใบนี้รับไปแล้วหรือถูกยกเลิกแล้ว ยกเลิกไม่ได้")
    if actor != doc.created_by and not is_manager:
        raise HttpError(403, "ยกเลิกได้เฉพาะผู้สร้างใบนี้ หรือผู้จัดการ")
    reason = reason.strip()
    if not reason:
        raise HttpError(422, "ต้องระบุเหตุผลที่ยกเลิก")
    for ln in doc.lines.select_related("variant__product", "material"):
        item = _item_from_line(ln)
        _add(doc.from_branch, item, ln.sent, StockMovement.Reason.TRANSFER_CANCEL if _is_product(item)
             else MaterialMovement.Reason.TRANSFER_CANCEL, doc, actor)
    doc.status = Document.Status.CANCELLED
    doc.cancel_reason = reason[:300]
    doc.closed_by, doc.closed_at = actor, timezone.now()
    doc.save(update_fields=["status", "cancel_reason", "closed_by", "closed_at"])
    return doc


def _item_from_line(ln: DocumentLine) -> dict:
    if ln.variant_id:
        return {"kind": "variant", "obj": ln.variant, "qty": ln.sent, "cost": None}
    return {"kind": "material", "obj": ln.material, "qty": ln.sent, "cost": None}


@transaction.atomic
def receive_transfer(doc: Document, *, actor: str, lines, substitute_reason: str = "") -> Document:
    """The branch counts what came off the truck. Every line must be answered (received, refused or lost)."""
    if doc.kind != Document.Kind.TRANSFER:
        raise HttpError(422, "ใบนี้ไม่ใช่ใบส่งสินค้า")
    if doc.status != Document.Status.SENT:
        raise HttpError(409, "ใบนี้รับไปแล้วหรือถูกยกเลิกแล้ว")
    by_id = {ln.id: ln for ln in doc.lines.select_related("variant__product", "material")}
    answers = {}
    for a in lines or []:
        try:
            answers[int(a.get("line_id"))] = a
        except (TypeError, ValueError):
            raise HttpError(422, "รายการที่ตอบไม่ถูกต้อง")
    if set(answers) != set(by_id):
        raise HttpError(422, "ต้องตอบทุกรายการในใบนี้")
    branch = doc.to_branch
    refused_lines = []
    lost_any = False
    for lid, ln in by_id.items():
        a = answers[lid]
        item = _item_from_line(ln)
        integer = _is_product(item)
        recv = _received(a.get("received"), sent=ln.sent, integer=integer)
        short = ln.sent - recv
        ln.received = recv
        ln.refused, ln.missing = Decimal(0), Decimal(0)
        ln.refuse_reason, ln.refuse_note = "", ""
        if short > 0:
            reason = (a.get("reason") or "").strip()
            if reason == LOST:
                ln.missing = short
                ln.refuse_reason = LOST
                lost_any = True
            elif reason in REFUSE_REASONS:
                note = (a.get("note") or "").strip()
                if reason == "other" and not note:
                    raise HttpError(422, "เลือก 'อื่นๆ' ต้องพิมพ์รายละเอียด")
                ln.refused = short
                ln.refuse_reason = reason
                ln.refuse_note = note[:300]
                refused_lines.append(ln)
            else:
                raise HttpError(422, f"{_item_name(item)} ไม่รับ {short:g} ต้องเลือกเหตุผล")
        if recv > 0:
            _add(branch, item, recv, StockMovement.Reason.TRANSFER_IN if integer else MaterialMovement.Reason.TRANSFER_IN, doc, actor)
        ln.save(update_fields=["received", "refused", "missing", "refuse_reason", "refuse_note"])
    refused_back = None
    if refused_lines:
        refused_back = _new_doc(kind=Document.Kind.RETURN, status=Document.Status.SENT_BACK, from_branch=branch,
                                to_branch=doc.from_branch, origin=doc, created_by=actor, sent_at=timezone.now(),
                                note=f"คืนจากใบ {doc.number}")
        for ln in refused_lines:
            DocumentLine.objects.create(document=refused_back, sent=ln.refused, refuse_reason=ln.refuse_reason,
                                        refuse_note=ln.refuse_note, **({"variant": ln.variant} if ln.variant_id else {"material": ln.material}))
        notify.return_sent(refused_back)
    all_sent = all(ln.received == ln.sent for ln in by_id.values())
    nothing = all((ln.received or 0) == 0 for ln in by_id.values())
    doc.status = (Document.Status.RECEIVED_FULL if all_sent else
                  Document.Status.RECEIVED_NONE if nothing else Document.Status.RECEIVED_PARTIAL)
    doc.closed_by, doc.closed_at = actor, timezone.now()
    doc.substitute_reason = substitute_reason.strip()[:300]
    doc.save(update_fields=["status", "closed_by", "closed_at", "substitute_reason"])
    if refused_lines or lost_any:
        notify.transfer_discrepancy(doc, refused_back)
    return doc


# ---------------------------------------------------------------- returns (RT-)

@transaction.atomic
def create_store_return(*, branch: Branch, note: str, lines, actor: str) -> Document:
    """A branch sends goods back on its own (near expiry, surplus). They leave its shelf now."""
    central = central_branch()
    if branch.id == central.id or branch.kind != Branch.Kind.STORE or not branch.is_active:
        raise HttpError(422, "เฉพาะสาขาที่ใช้งานอยู่ส่งคืนคลังกลางได้")
    items = _resolve_lines(lines)
    doc = _new_doc(kind=Document.Kind.RETURN, status=Document.Status.SENT_BACK, from_branch=branch, to_branch=central,
                   note=note[:500], created_by=actor, sent_at=timezone.now())
    for it in items:
        DocumentLine.objects.create(document=doc, sent=it["qty"], **_line_kwargs(it))
        _take(branch, it, it["qty"], StockMovement.Reason.RETURN_OUT if _is_product(it) else MaterialMovement.Reason.RETURN_OUT,
              doc, actor)
    notify.return_sent(doc)
    return doc


@transaction.atomic
def receive_return(doc: Document, *, actor: str, lines) -> Document:
    """Central warehouse receives goods coming back. Each line: put back on the shelf, thrown away, or lost."""
    if doc.kind != Document.Kind.RETURN:
        raise HttpError(422, "ใบนี้ไม่ใช่ใบคืนสินค้า")
    if doc.status != Document.Status.SENT_BACK:
        raise HttpError(409, "ใบนี้รับไปแล้ว")
    central = doc.to_branch
    by_id = {ln.id: ln for ln in doc.lines.select_related("variant__product", "material")}
    answers = {}
    for a in lines or []:
        try:
            answers[int(a.get("line_id"))] = a
        except (TypeError, ValueError):
            raise HttpError(422, "รายการที่ตอบไม่ถูกต้อง")
    if set(answers) != set(by_id):
        raise HttpError(422, "ต้องตอบทุกรายการในใบนี้")
    for lid, ln in by_id.items():
        a = answers[lid]
        item = _item_from_line(ln)
        integer = _is_product(item)
        restock = _received(a.get("restock", 0), sent=ln.sent, integer=integer)
        discard = _received(a.get("discard", 0), sent=ln.sent, integer=integer)
        if restock + discard > ln.sent:
            raise HttpError(422, f"{_item_name(item)}: เข้าสต็อกกับทิ้งรวมเกินที่ส่งมา")
        ln.restocked = restock
        ln.discarded = discard
        ln.missing = ln.sent - restock - discard
        ln.received = restock + discard
        if restock > 0:
            _add(central, item, restock, StockMovement.Reason.RETURN_IN if integer else MaterialMovement.Reason.RETURN_IN, doc, actor)
        ln.save(update_fields=["restocked", "discarded", "missing", "received"])
    doc.status = Document.Status.CLOSED
    doc.closed_by, doc.closed_at = actor, timezone.now()
    doc.save(update_fields=["status", "closed_by", "closed_at"])
    return doc


# ---------------------------------------------------------------- overdue slips

def overdue_slips(now=None):
    now = now or timezone.now()
    return Document.objects.filter(status__in=[Document.Status.SENT, Document.Status.SENT_BACK],
                                   sent_at__lt=now - OVERDUE_AFTER, overdue_alerted_at__isnull=True)


def alert_overdue(now=None) -> int:
    """Tell the managers once about each slip nobody has confirmed for a day."""
    n = 0
    for doc in overdue_slips(now):
        notify.stock_overdue(doc)
        doc.overdue_alerted_at = timezone.now()
        doc.save(update_fields=["overdue_alerted_at"])
        n += 1
    return n
