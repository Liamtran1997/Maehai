import re
from collections import Counter
from datetime import date

from django.db import transaction
from ninja.errors import HttpError

from maehai.catalog.models import ProductVariant
from maehai.core.money import vat_included
from maehai.inventory import services as stock
from maehai.notifications import events as notify
from maehai.shipping.models import ShippingMethod
from maehai.shipping.schedule import validate_fulfillment_date

from .models import TRANSITIONS, Order, OrderEvent, OrderItem, OrderStatus

MAX_QTY_PER_LINE = 99
MAX_LINES = 40


def log(order: Order, kind: str, detail: str = "", actor: str = "customer") -> None:
    OrderEvent.objects.create(order=order, kind=kind, detail=detail, actor=actor)


def normalize_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("66") and len(digits) in (11, 12):  # +66 812345678
        digits = "0" + digits[2:]
    if not re.fullmatch(r"0\d{8,9}", digits):
        raise HttpError(422, "เบอร์โทรศัพท์ไม่ถูกต้อง")
    return digits


def _validate_postal(code: str) -> str:
    if code and not re.fullmatch(r"\d{5}", code):
        raise HttpError(422, "เลขไปรษณีย์ต้องมี 5 หลัก")
    return code


@transaction.atomic
def create_order(*, items: list[tuple[str, int]], customer_name: str, phone: str, shipping_code: str,
                 requested_date: date, address: dict, note: str = "") -> Order:
    if not items or len(items) > MAX_LINES:
        raise HttpError(422, "ตะกร้าว่างหรือมีรายการมากเกินไป")
    qty = Counter()
    for sku, q in items:
        if not 1 <= q <= MAX_QTY_PER_LINE:
            raise HttpError(422, f"จำนวนต้องอยู่ระหว่าง 1 ถึง {MAX_QTY_PER_LINE}")
        qty[sku] += q
    if any(q > MAX_QTY_PER_LINE for q in qty.values()):
        raise HttpError(422, f"จำนวนต้องอยู่ระหว่าง 1 ถึง {MAX_QTY_PER_LINE}")

    variants = {v.sku: v for v in ProductVariant.objects.select_related("product")
                .filter(sku__in=qty, is_active=True, product__is_active=True)}
    missing = sorted(set(qty) - set(variants))
    if missing:
        raise HttpError(422, f"สินค้าบางรายการหมดหรือไม่มีในระบบ: {', '.join(missing)}")

    try:
        method = ShippingMethod.objects.get(code=shipping_code, is_active=True)
    except ShippingMethod.DoesNotExist:
        raise HttpError(422, "วิธีรับสินค้าไม่ถูกต้อง") from None

    err = validate_fulfillment_date(requested_date)
    if err:
        raise HttpError(422, err)

    address = {k: (address.get(k) or "").strip() for k in ("address_line", "subdistrict", "district", "province", "postal_code")}
    _validate_postal(address["postal_code"])
    if method.requires_address and not all(address[k] for k in ("address_line", "province", "postal_code")):
        raise HttpError(422, "กรุณากรอกที่อยู่จัดส่งให้ครบ")

    subtotal = sum(variants[s].price_satang * q for s, q in qty.items())
    quoted = method.fee_is_quoted
    order = Order.objects.create(
        customer_name=customer_name.strip(), phone=normalize_phone(phone), shipping_method=method,
        requested_date=requested_date, note=note.strip(), subtotal_satang=subtotal,
        shipping_fee_satang=None if quoted else 0,
        vat_satang=0 if quoted else vat_included(subtotal),
        status=OrderStatus.PENDING_QUOTE if quoted else OrderStatus.WAITING_PAYMENT,
        **address,
    )
    OrderItem.objects.bulk_create([
        OrderItem(order=order, variant=variants[s], product_name=variants[s].product.name,
                  variant_label=variants[s].label, sku=s, unit_price_satang=variants[s].price_satang, quantity=q)
        for s, q in qty.items()
    ])
    order.fulfillment_branch = stock.reserve_for_order(order, [(variants[s], q) for s, q in qty.items()], method)
    order.save(update_fields=["fulfillment_branch"])
    log(order, "created", f"{len(qty)} รายการ ฿{subtotal / 100:,.2f}")
    notify.order_created(order)
    return order


def change_status(order: Order, to: str, *, actor: str, detail: str = "", system: bool = False) -> Order:
    """The only place status changes. `system=True` lets internal flows make money transitions."""
    if to not in TRANSITIONS[order.status]:
        raise HttpError(409, f"เปลี่ยนสถานะจาก {OrderStatus(order.status).label} เป็น {OrderStatus(to).label} ไม่ได้")
    if not system and to in (OrderStatus.PAID, OrderStatus.WAITING_PAYMENT):
        raise HttpError(409, "สถานะนี้เปลี่ยนผ่านการแจ้งค่าส่งหรือการยืนยันชำระเงินเท่านั้น")
    order.status = to
    order.save(update_fields=["status", "updated_at"])
    log(order, "status", OrderStatus(to).label + (f": {detail}" if detail else ""), actor=actor)
    return order


@transaction.atomic
def quote_fee(order: Order, fee_satang: int, actor: str) -> Order:
    """Staff set the shipping fee. Moves the order to waiting_payment and voids any unpaid QR (the amount changed)."""
    from maehai.payments.models import PaymentStatus

    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.status not in (OrderStatus.PENDING_QUOTE, OrderStatus.WAITING_PAYMENT):
        raise HttpError(409, "แก้ค่าจัดส่งไม่ได้แล้ว")
    if order.payments.filter(status=PaymentStatus.SLIP_SUBMITTED).exists():
        raise HttpError(409, "ลูกค้าแนบสลิปแล้ว ตรวจสลิปก่อนจึงจะแก้ค่าจัดส่งได้")
    order.payments.filter(status=PaymentStatus.PENDING).update(status=PaymentStatus.EXPIRED)
    order.shipping_fee_satang = fee_satang
    order.vat_satang = vat_included(order.subtotal_satang + fee_satang)
    was = order.status
    order.status = OrderStatus.WAITING_PAYMENT
    order.save(update_fields=["shipping_fee_satang", "vat_satang", "status", "updated_at"])
    log(order, "fee_quoted", f"ค่าจัดส่ง ฿{fee_satang / 100:,.2f}" + ("" if was == OrderStatus.PENDING_QUOTE else " (แก้ไข)"), actor=actor)
    notify.fee_quoted(order)
    return order


@transaction.atomic
def staff_set_status(order: Order, to: str, actor: str, tracking_ref: str = "") -> Order:
    order = Order.objects.select_for_update().get(pk=order.pk)
    if tracking_ref:
        order.tracking_ref = tracking_ref.strip()[:60]
        order.save(update_fields=["tracking_ref"])
    change_status(order, to, actor=actor, detail=tracking_ref)
    if to == OrderStatus.CANCELLED:
        from maehai.payments.models import PaymentStatus
        order.payments.filter(status=PaymentStatus.PENDING).update(status=PaymentStatus.EXPIRED)
        stock.release_for_order(order)
        notify.cancelled(order)
    elif to in (OrderStatus.SHIPPED, OrderStatus.DONE):
        stock.commit_for_order(order, actor)   # no-op if already committed when it shipped
        if to == OrderStatus.SHIPPED:
            notify.shipped(order)
    return order


def find_by_token(number: str, token: str) -> Order:
    order = Order.objects.select_related("shipping_method").prefetch_related("items", "events", "payments").filter(number=number).first()
    # Constant-ish response: same 404 for unknown number and wrong token.
    import secrets
    if order is None or not secrets.compare_digest(order.public_token, token):
        raise HttpError(404, "ไม่พบคำสั่งซื้อ")
    return order


