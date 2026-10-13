"""Stock rules.

 reserve   when an order is placed          (promise units; fails if not enough)
 commit    when the goods leave the shop    (shipped, or handed over at the counter)
 release   when the order is cancelled      (give the promise back)

Only variants with track_stock=True are counted. A level may also have a daily ONLINE quota: the shop sells at most
that many units a day from the branch, so the counter keeps the rest. The quota is counted when an order reserves
and handed back if the order is cancelled the same day. The "enough stock" check is one atomic conditional UPDATE, so two
customers buying the last item at the same moment cannot both succeed, on SQLite and Postgres alike.
"""
import csv
import io
from collections import defaultdict

from django.conf import settings
from django.db import transaction
from django.db.models import F, IntegerField, Value
from django.db.models.functions import Coalesce, Greatest
from django.utils import timezone
from ninja.errors import HttpError

from maehai.notifications import events as notify

from .models import Branch, OnlineSale, RestockRequest, StockLevel, StockMovement, StockReservation


class _Short(Exception):
    def __init__(self, shortages):
        self.shortages = shortages


def available_map(variant_ids) -> dict[int, int | None]:
    """Units a customer could still buy, summed over active branches (stock, capped by each branch's daily online
    quota). None = not counted (always available)."""
    from maehai.catalog.models import ProductVariant

    ids = list(variant_ids)
    tracked = set(ProductVariant.objects.filter(pk__in=ids, track_stock=True).values_list("pk", flat=True))
    levels = list(StockLevel.objects.filter(variant_id__in=tracked, branch__is_active=True))
    sold = dict(OnlineSale.objects.filter(level__in=levels, day=timezone.localdate()).values_list("level_id", "units"))
    totals: dict[int, int] = defaultdict(int)
    for lv in levels:
        totals[lv.variant_id] += lv.online_available(sold.get(lv.id, 0))
    return {i: (totals.get(i, 0) if i in tracked else None) for i in ids}


def _try_reserve(order, lines, branch) -> list[str]:
    """All-or-nothing reservation at one branch. Returns shortage descriptions (empty = success)."""
    today = timezone.localdate()
    try:
        with transaction.atomic():
            shortages = []
            for variant, qty in lines:
                if not variant.track_stock:
                    continue
                ok = StockLevel.objects.filter(branch=branch, variant=variant, on_hand__gte=F("reserved") + qty) \
                    .update(reserved=F("reserved") + qty)
                quota_day = None
                if ok:
                    lv = StockLevel.objects.get(branch=branch, variant=variant)
                    if lv.online_quota is not None:
                        # One conditional UPDATE, like the stock check, so two orders cannot both take the last quota unit.
                        row, _ = OnlineSale.objects.get_or_create(level=lv, day=today)
                        ok = OnlineSale.objects.filter(pk=row.pk, units__lte=lv.online_quota - qty).update(units=F("units") + qty)
                        quota_day = today if ok else None
                if not ok:
                    have = StockLevel.objects.filter(branch=branch, variant=variant).first()
                    left = 0
                    if have:
                        sold = OnlineSale.objects.filter(level=have, day=today).values_list("units", flat=True).first() or 0
                        left = have.online_available(sold)
                    shortages.append(f"{variant.product.name} ({variant.label}) เหลือ {left}")
                    continue
                StockReservation.objects.create(order=order, variant=variant, branch=branch, quantity=qty, quota_day=quota_day)
            if shortages:
                raise _Short(shortages)
    except _Short as s:
        return s.shortages
    return []


def reserve_for_order(order, lines, method) -> Branch | None:
    """Pick the branch that fills the order and reserve there. Pickup uses the customer's branch. Delivery tries the
    default branch first, then the others, and uses the first one that can fill the WHOLE order."""
    if method.branch_id:
        candidates = [method.branch]
    else:
        branches = list(Branch.objects.filter(is_active=True))
        branches.sort(key=lambda b: (b.code != settings.DEFAULT_FULFILLMENT_BRANCH, b.sort_order))
        candidates = branches
    if not candidates:
        return None
    first_shortages: list[str] = []
    for b in candidates:
        shortages = _try_reserve(order, lines, b)
        if not shortages:
            for variant, _ in lines:
                if variant.track_stock:
                    refresh_low_alert(b, variant, decreased=True)
            return b
        first_shortages = first_shortages or shortages
    raise HttpError(409, "สินค้าไม่พอสำหรับคำสั่งซื้อนี้: " + ", ".join(first_shortages))


def refresh_low_alert(branch, variant, *, decreased: bool) -> None:
    """Keep the low-stock alert in step with the level. Staff are told ONCE when available falls to the line
    (only a decrease can trigger it), and told again only after stock has been back above the line."""
    lv = StockLevel.objects.filter(branch=branch, variant=variant).first()
    if lv is None:
        return
    low = lv.available <= lv.threshold
    if low and decreased and not lv.low_alerted:
        if StockLevel.objects.filter(pk=lv.pk, low_alerted=False).update(low_alerted=True):
            notify.low_stock(variant, branch, lv.available)
    elif not low and lv.low_alerted:
        StockLevel.objects.filter(pk=lv.pk, low_alerted=True).update(low_alerted=False)


@transaction.atomic
def release_for_order(order, *, announce: bool = True) -> None:
    """announce=False when the units are about to be reserved again (moving branch), so nobody is told "back in stock"."""
    for r in order.reservations.select_for_update().filter(state=StockReservation.State.RESERVED):
        StockLevel.objects.filter(branch=r.branch, variant=r.variant).update(reserved=F("reserved") - r.quantity)
        if r.quota_day == timezone.localdate():
            # Cancelled the same day: the online quota unit goes back too. An earlier day's quota is already spent.
            OnlineSale.objects.filter(level__branch=r.branch, level__variant=r.variant, day=r.quota_day) \
                .update(units=Greatest(F("units") - r.quantity, Value(0)))
        r.state = StockReservation.State.RELEASED
        r.save(update_fields=["state"])
        refresh_low_alert(r.branch, r.variant, decreased=False)
        if announce:
            notify_if_restocked(r.variant)


@transaction.atomic
def commit_for_order(order, actor: str) -> None:
    """Goods have left: take them out of on_hand for good and write the sale into the ledger."""
    for r in order.reservations.select_for_update().filter(state=StockReservation.State.RESERVED):
        StockLevel.objects.filter(branch=r.branch, variant=r.variant).update(
            on_hand=F("on_hand") - r.quantity, reserved=F("reserved") - r.quantity)
        lv = StockLevel.objects.get(branch=r.branch, variant=r.variant)
        StockMovement.objects.create(branch=r.branch, variant=r.variant, delta=-r.quantity, on_hand_after=lv.on_hand,
                                     reason=StockMovement.Reason.SALE, order=order, actor=actor)
        r.state = StockReservation.State.COMMITTED
        r.save(update_fields=["state"])


@transaction.atomic
def reassign_branch(order, branch: Branch) -> None:
    """Move an unshipped delivery order to another branch. Keeps the old reservation if the new branch cannot fill it."""
    from maehai.orders.models import OrderItem

    if order.fulfillment_branch_id == branch.id:
        return
    held = list(order.reservations.filter(state=StockReservation.State.RESERVED).select_related("variant", "branch"))
    lines = [(r.variant, r.quantity) for r in held]
    sid = transaction.savepoint()
    release_for_order(order, announce=False)
    shortages = _try_reserve(order, lines, branch)
    if shortages:
        transaction.savepoint_rollback(sid)
        raise HttpError(409, f"{branch.name} มีสินค้าไม่พอ: " + ", ".join(shortages))
    transaction.savepoint_commit(sid)
    order.fulfillment_branch = branch
    order.save(update_fields=["fulfillment_branch", "updated_at"])
    _ = OrderItem  # (imported for readers: items themselves never change)


def _level_for_update(branch, variant) -> StockLevel:
    lv, _ = StockLevel.objects.get_or_create(branch=branch, variant=variant)
    return StockLevel.objects.select_for_update().get(pk=lv.pk)


@transaction.atomic
def adjust(*, branch: Branch, variant, reason: str, actor: str, quantity: int, note: str = "") -> StockLevel:
    """Staff stock changes. RECEIVE adds `quantity`. WASTE removes it. COUNT sets on_hand to `quantity`.
    Never drops below what is already promised to orders."""
    R = StockMovement.Reason
    if reason == R.RECEIVE:
        raise HttpError(422, "รับของเข้าต้องทำผ่านใบรับสินค้าที่คลังกลาง")
    if reason not in (R.WASTE, R.COUNT):
        raise HttpError(422, "เหตุผลไม่ถูกต้อง")
    if quantity < 0 or (reason != R.COUNT and quantity == 0):
        raise HttpError(422, "จำนวนไม่ถูกต้อง")
    lv = _level_for_update(branch, variant)
    new = {R.RECEIVE: lv.on_hand + quantity, R.WASTE: lv.on_hand - quantity, R.COUNT: quantity}[reason]
    if new < lv.reserved:
        raise HttpError(409, f"สต็อกต่ำกว่าที่จองไว้ ({lv.reserved}) ไม่ได้ ต้องยกเลิกหรือย้ายคำสั่งซื้อก่อน")
    delta = new - lv.on_hand
    if delta == 0:
        return lv
    lv.on_hand = new
    lv.save(update_fields=["on_hand"])
    StockMovement.objects.create(branch=branch, variant=variant, delta=delta, on_hand_after=new, reason=reason, note=note[:200], actor=actor)
    refresh_low_alert(branch, variant, decreased=delta < 0)
    if delta > 0:
        notify_if_restocked(variant)
    return lv


@transaction.atomic
def adjust_material(*, branch: Branch, material, reason: str, quantity, actor: str, note: str = ""):
    """Materials and supplies: waste, consumption ("เบิกใช้") or a stock count. Receipts go through a document."""
    from decimal import Decimal

    from .models import MaterialLevel, MaterialMovement

    R = MaterialMovement.Reason
    if reason not in (R.WASTE, R.CONSUME, R.COUNT):
        raise HttpError(422, "เหตุผลไม่ถูกต้อง")
    qty = Decimal(str(quantity)).quantize(Decimal("0.001"))
    if qty < 0 or (reason != R.COUNT and qty == 0):
        raise HttpError(422, "จำนวนไม่ถูกต้อง")
    ml, _ = MaterialLevel.objects.get_or_create(branch=branch, material=material)
    ml = MaterialLevel.objects.select_for_update().get(pk=ml.pk)
    if reason == R.COUNT:
        new = qty
    else:
        new = ml.on_hand - qty if reason == R.WASTE or reason == R.CONSUME else ml.on_hand + qty
    if new < 0:
        raise HttpError(409, f"{material.name} ที่{branch.name}มีแค่ {ml.on_hand:g} {material.unit}")
    delta = new - ml.on_hand
    if delta == 0:
        return ml
    ml.on_hand = new
    ml.save(update_fields=["on_hand"])
    MaterialMovement.objects.create(branch=branch, material=material, delta=delta, on_hand_after=new, reason=reason,
                                    note=note[:200], actor=actor)
    return ml


def low_stock_count() -> int:
    """Tracked variant+branch pairs at or under their low-stock line (shown on the dashboard)."""
    line = Coalesce("low_stock_threshold", Value(settings.LOW_STOCK_THRESHOLD), output_field=IntegerField())
    return StockLevel.objects.filter(variant__track_stock=True, variant__is_active=True, branch__is_active=True) \
        .annotate(line=line).filter(on_hand__lte=F("reserved") + F("line")).count()


def request_restock_alert(variant, line_user_id: str) -> bool:
    """Returns False if this customer is already waiting for this variant."""
    _, created = RestockRequest.objects.get_or_create(variant=variant, line_user_id=line_user_id, notified_at=None)
    return created


def notify_if_restocked(variant) -> int:
    """Message everyone waiting for this variant once it can be bought again. Returns how many were told.
    Called after anything that can raise availability: receiving stock, a count, a cancelled order."""
    from django.utils import timezone

    if not variant.track_stock:
        return 0
    if (available_map([variant.id]).get(variant.id) or 0) <= 0:
        return 0
    waiting = list(RestockRequest.objects.select_for_update().filter(variant=variant, notified_at__isnull=True))
    for r in waiting:
        notify.restocked(variant, r.line_user_id)
    RestockRequest.objects.filter(pk__in=[r.pk for r in waiting]).update(notified_at=timezone.now())
    return len(waiting)


# ---------- per-level settings, counter sold-out ----------
@transaction.atomic
def set_level_settings(*, branch: Branch, variant, online_quota: int | None, low_stock_threshold: int | None) -> StockLevel:
    """Daily online quota and low-stock line for one variant at one branch. None = no quota / use the shop default."""
    for v in (online_quota, low_stock_threshold):
        if v is not None and not 0 <= v <= 1_000_000:
            raise HttpError(422, "ตัวเลขไม่ถูกต้อง")
    lv = _level_for_update(branch, variant)
    lv.online_quota, lv.low_stock_threshold = online_quota, low_stock_threshold
    lv.save(update_fields=["online_quota", "low_stock_threshold"])
    refresh_low_alert(branch, variant, decreased=False)      # a higher line is not an alert, but a lower one can clear it
    return lv


@transaction.atomic
def sold_out_at_counter(*, branch: Branch, variant, actor: str, note: str = "") -> StockLevel:
    """The counter sold the rest. Take on_hand down to what online orders have already been promised, so the shop
    stops selling at once and the orders already placed can still be filled."""
    if not variant.track_stock:
        raise HttpError(409, "สินค้านี้ยังไม่ได้เปิดนับสต็อก")
    lv = _level_for_update(branch, variant)
    delta = lv.reserved - lv.on_hand
    if delta == 0:
        return lv
    lv.on_hand = lv.reserved
    lv.save(update_fields=["on_hand"])
    StockMovement.objects.create(branch=branch, variant=variant, delta=delta, on_hand_after=lv.on_hand,
                                 reason=StockMovement.Reason.COUNTER_SALE, note=(note or "หมดหน้าร้าน")[:200], actor=actor)
    refresh_low_alert(branch, variant, decreased=True)
    return lv


# ---------- opening stock from a CSV file ----------
IMPORT_COLUMNS = ["sku", "branch_code", "tracking", "on_hand", "online_quota", "low_stock_threshold"]
IMPORT_MAX_ROWS = 2000
IMPORT_MAX_CHARS = 500_000
_NUMBER_MAX = 1_000_000


def _number(raw: str | None, label: str, errors: list[str]) -> int | None:
    raw = (raw or "").strip()
    if raw == "":
        return None
    if not raw.isdigit() or int(raw) > _NUMBER_MAX:
        errors.append(f"{label} ต้องเป็นจำนวนเต็มตั้งแต่ 0 ถึง {_NUMBER_MAX}")
        return None
    return int(raw)


def parse_import(text: str, allowed_branch_codes=None) -> dict:
    """Read and check a stock file without writing anything. Returns the rows with their problems."""
    from maehai.catalog.models import ProductVariant

    if len(text) > IMPORT_MAX_CHARS:
        raise HttpError(422, "ไฟล์ใหญ่เกินไป")
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    header = [h.strip().lower() for h in (reader.fieldnames or [])]
    missing = [c for c in ("sku", "branch_code", "tracking") if c not in header]
    if missing:
        raise HttpError(422, "ไฟล์ขาดคอลัมน์: " + ", ".join(missing))
    reader.fieldnames = header
    raw_rows = list(reader)
    if len(raw_rows) > IMPORT_MAX_ROWS:
        raise HttpError(422, f"ไฟล์มีได้ไม่เกิน {IMPORT_MAX_ROWS} แถว")

    variants = {v.sku: v for v in ProductVariant.objects.select_related("product")
                .filter(sku__in={(r.get("sku") or "").strip() for r in raw_rows})}
    branches = {b.code: b for b in Branch.objects.filter(is_active=True)}
    levels = {(lv.branch.code, lv.variant.sku): lv for lv in StockLevel.objects.select_related("branch", "variant")
              .filter(variant__sku__in=variants.keys())}
    seen: set[tuple[str, str]] = set()
    tracking_of: dict[str, str] = {}
    rows = []
    for n, r in enumerate(raw_rows, start=2):       # line 1 is the header
        errors: list[str] = []
        sku = (r.get("sku") or "").strip()
        code = (r.get("branch_code") or "").strip()
        tracking = (r.get("tracking") or "").strip().lower()
        on_hand = _number(r.get("on_hand"), "on_hand", errors)
        quota = _number(r.get("online_quota"), "online_quota", errors)
        line = _number(r.get("low_stock_threshold"), "low_stock_threshold", errors)
        v = variants.get(sku)
        if v is None:
            errors.append("ไม่พบ SKU นี้")
        if code not in branches:
            errors.append("ไม่พบสาขานี้")
        elif allowed_branch_codes is not None and code not in allowed_branch_codes:
            errors.append("ไม่มีสิทธิ์สาขานี้")
        if tracking == "daily":
            errors.append("ยังไม่รองรับ tracking=daily (ใช้ none หรือ stock)")
        elif tracking not in ("none", "stock"):
            errors.append("tracking ต้องเป็น none หรือ stock")
        if (sku, code) in seen:
            errors.append("SKU และสาขานี้ซ้ำในไฟล์")
        seen.add((sku, code))
        if tracking in ("none", "stock"):
            if sku in tracking_of and tracking_of[sku] != tracking:
                errors.append("SKU เดียวกันกำหนด tracking ไม่ตรงกันในไฟล์")
            tracking_of.setdefault(sku, tracking)
        current = levels.get((code, sku))
        if tracking == "stock" and on_hand is None and (r.get("on_hand") or "").strip() == "":
            errors.append("tracking=stock ต้องระบุ on_hand")
        if tracking == "none" and any(x is not None for x in (on_hand, quota, line)):
            errors.append("tracking=none ต้องเว้น on_hand, online_quota, low_stock_threshold ว่างไว้")
        if on_hand is not None and current and on_hand < current.reserved:
            errors.append(f"on_hand ต่ำกว่าที่จองไว้ ({current.reserved})")
        rows.append({
            "line": n, "sku": sku, "branch_code": code, "tracking": tracking,
            "product_name": v.product.name if v else "", "variant_label": v.label if v else "",
            "on_hand": on_hand, "online_quota": quota, "low_stock_threshold": line,
            "current_on_hand": current.on_hand if current else 0,
            "delta": (on_hand - (current.on_hand if current else 0)) if on_hand is not None else None,
            "errors": errors,
        })
    bad = sum(1 for r in rows if r["errors"])
    return {"rows": rows, "total": len(rows), "error_count": bad, "ok_count": len(rows) - bad}


@transaction.atomic
def apply_import(text: str, *, actor: str, allowed_branch_codes=None) -> dict:
    """Write a checked stock file. Refuses the whole file if any row has a problem, so a half-applied file never happens."""
    from maehai.catalog.models import ProductVariant

    parsed = parse_import(text, allowed_branch_codes)
    if parsed["error_count"]:
        raise HttpError(422, f"ไฟล์ยังมี {parsed['error_count']} แถวที่ผิด แก้ก่อนแล้วลองใหม่")
    branches = {b.code: b for b in Branch.objects.filter(is_active=True)}
    changed = 0
    for r in parsed["rows"]:
        variant = ProductVariant.objects.select_related("product").get(sku=r["sku"])
        branch = branches[r["branch_code"]]
        want_tracked = r["tracking"] == "stock"
        if variant.track_stock != want_tracked:
            variant.track_stock = want_tracked
            variant.save(update_fields=["track_stock"])
            changed += 1
        if not want_tracked:
            continue
        lv = _level_for_update(branch, variant)
        delta = r["on_hand"] - lv.on_hand
        if delta:
            first = not StockMovement.objects.filter(branch=branch, variant=variant).exists()
            lv.on_hand = r["on_hand"]
            lv.save(update_fields=["on_hand"])
            StockMovement.objects.create(
                branch=branch, variant=variant, delta=delta, on_hand_after=lv.on_hand, actor=actor, note="นำเข้าจากไฟล์ CSV",
                reason=StockMovement.Reason.OPENING if first else StockMovement.Reason.COUNT)
            changed += 1
        if (lv.online_quota, lv.low_stock_threshold) != (r["online_quota"], r["low_stock_threshold"]):
            lv.online_quota, lv.low_stock_threshold = r["online_quota"], r["low_stock_threshold"]
            lv.save(update_fields=["online_quota", "low_stock_threshold"])
            changed += 1
        refresh_low_alert(branch, variant, decreased=delta < 0)
        if delta > 0:
            notify_if_restocked(variant)
    return {"rows": parsed["total"], "changed": changed}


def import_template(allowed_branch_codes=None) -> str:
    """A CSV with every active size at every active branch and today's numbers, ready to fill in."""
    from maehai.catalog.models import ProductVariant

    levels = {(lv.branch_id, lv.variant_id): lv for lv in StockLevel.objects.all()}
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(IMPORT_COLUMNS)
    branches = [b for b in Branch.objects.filter(is_active=True)
                if allowed_branch_codes is None or b.code in allowed_branch_codes]
    for v in ProductVariant.objects.filter(is_active=True, product__is_active=True).select_related("product") \
            .order_by("product__sort_order", "product__name", "sort_order"):
        for b in branches:
            lv = levels.get((b.id, v.id))
            if v.track_stock:
                w.writerow([v.sku, b.code, "stock", lv.on_hand if lv else 0,
                            "" if not lv or lv.online_quota is None else lv.online_quota,
                            "" if not lv or lv.low_stock_threshold is None else lv.low_stock_threshold])
            else:
                w.writerow([v.sku, b.code, "none", "", "", ""])
    return "﻿" + out.getvalue()
