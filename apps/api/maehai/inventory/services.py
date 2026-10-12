"""Stock rules.

 reserve   when an order is placed          (promise units; fails if not enough)
 commit    when the goods leave the shop    (shipped, or handed over at the counter)
 release   when the order is cancelled      (give the promise back)

Only variants with track_stock=True are counted. The "enough stock" check is one atomic conditional UPDATE, so two
customers buying the last item at the same moment cannot both succeed, on SQLite and Postgres alike.
"""
from django.conf import settings
from django.db import transaction
from django.db.models import F, Sum
from ninja.errors import HttpError

from maehai.notifications import events as notify

from .models import Branch, StockLevel, StockMovement, StockReservation


class _Short(Exception):
    def __init__(self, shortages):
        self.shortages = shortages


def available_map(variant_ids) -> dict[int, int | None]:
    """Units a customer could still buy, summed over active branches. None = not counted (always available)."""
    from maehai.catalog.models import ProductVariant

    ids = list(variant_ids)
    tracked = set(ProductVariant.objects.filter(pk__in=ids, track_stock=True).values_list("pk", flat=True))
    sums = {r["variant_id"]: r["a"] for r in StockLevel.objects.filter(variant_id__in=tracked, branch__is_active=True)
            .values("variant_id").annotate(a=Sum(F("on_hand") - F("reserved")))}
    return {i: (sums.get(i, 0) if i in tracked else None) for i in ids}


def _try_reserve(order, lines, branch) -> list[str]:
    """All-or-nothing reservation at one branch. Returns shortage descriptions (empty = success)."""
    try:
        with transaction.atomic():
            shortages = []
            for variant, qty in lines:
                if not variant.track_stock:
                    continue
                ok = StockLevel.objects.filter(branch=branch, variant=variant, on_hand__gte=F("reserved") + qty) \
                    .update(reserved=F("reserved") + qty)
                if not ok:
                    have = StockLevel.objects.filter(branch=branch, variant=variant).first()
                    shortages.append(f"{variant.product.name} ({variant.label}) เหลือ {have.available if have else 0}")
                    continue
                StockReservation.objects.create(order=order, variant=variant, branch=branch, quantity=qty)
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
            _low_stock_check(lines, b)
            return b
        first_shortages = first_shortages or shortages
    raise HttpError(409, "สินค้าไม่พอสำหรับคำสั่งซื้อนี้: " + ", ".join(first_shortages))


def _low_stock_check(lines, branch) -> None:
    """Tell staff once when an item drops to the low-stock line (not on every sale below it)."""
    limit = settings.LOW_STOCK_THRESHOLD
    for variant, qty in lines:
        if not variant.track_stock:
            continue
        lv = StockLevel.objects.get(branch=branch, variant=variant)
        if lv.available + qty > limit >= lv.available:
            notify.low_stock(variant, branch, lv.available)


@transaction.atomic
def release_for_order(order) -> None:
    for r in order.reservations.select_for_update().filter(state=StockReservation.State.RESERVED):
        StockLevel.objects.filter(branch=r.branch, variant=r.variant).update(reserved=F("reserved") - r.quantity)
        r.state = StockReservation.State.RELEASED
        r.save(update_fields=["state"])


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
    release_for_order(order)
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
    if reason not in (R.RECEIVE, R.WASTE, R.COUNT):
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
    return lv


@transaction.atomic
def transfer(*, source: Branch, dest: Branch, variant, quantity: int, actor: str, note: str = "") -> None:
    if source.id == dest.id or quantity <= 0:
        raise HttpError(422, "ข้อมูลการโอนไม่ถูกต้อง")
    a = _level_for_update(source, variant)
    if a.available < quantity:
        raise HttpError(409, f"{source.name} มีของพร้อมขายแค่ {a.available}")
    b = _level_for_update(dest, variant)
    a.on_hand -= quantity
    b.on_hand += quantity
    a.save(update_fields=["on_hand"])
    b.save(update_fields=["on_hand"])
    R = StockMovement.Reason
    StockMovement.objects.create(branch=source, variant=variant, delta=-quantity, on_hand_after=a.on_hand, reason=R.TRANSFER_OUT, note=note[:200], actor=actor)
    StockMovement.objects.create(branch=dest, variant=variant, delta=quantity, on_hand_after=b.on_hand, reason=R.TRANSFER_IN, note=note[:200], actor=actor)


def low_stock_count() -> int:
    """Tracked variant+branch pairs at or under the low-stock line (shown on the dashboard)."""
    return StockLevel.objects.filter(variant__track_stock=True, variant__is_active=True, branch__is_active=True,
                                     on_hand__lte=F("reserved") + settings.LOW_STOCK_THRESHOLD).count()
