"""Checkout preview: lets the customer see the discount before placing the order."""
from ninja import Router, Schema
from ninja.errors import HttpError

from maehai.catalog.models import ProductVariant
from maehai.catalog.pricing import prices_for
from maehai.core import ratelimit
from maehai.orders.schemas import ItemIn
from maehai.orders.services import MAX_LINES, normalize_phone

from . import services
from .services import CouponError

router = Router(tags=["coupons"])


class ValidateIn(Schema):
    code: str
    items: list[ItemIn]
    phone: str = ""        # optional here; the per-phone limit is always enforced when the order is placed


class ValidateOut(Schema):
    code: str
    label: str
    subtotal_satang: int
    discount_satang: int
    goods_total_satang: int


@router.post("/validate", response=ValidateOut)
def validate(request, data: ValidateIn):
    ip = ratelimit.client_ip(request)
    ratelimit.hit("coupon_check_ip", ip)
    ratelimit.blocked("coupon_fail_ip", ip)             # guessing codes is throttled
    if not data.items or len(data.items) > MAX_LINES:
        raise HttpError(422, "ตะกร้าว่างหรือมีรายการมากเกินไป")

    qty: dict[str, int] = {}
    for i in data.items:
        if not 1 <= i.quantity <= 99:
            raise HttpError(422, "จำนวนต้องอยู่ระหว่าง 1 ถึง 99")
        qty[i.sku] = qty.get(i.sku, 0) + i.quantity
    variants = {v.sku: v for v in ProductVariant.objects.select_related("product__category")
                .filter(sku__in=qty, is_active=True, product__is_active=True, product__category__is_active=True)}
    if set(qty) - set(variants):
        raise HttpError(422, "สินค้าบางรายการหมดหรือไม่มีในระบบ")
    prices = prices_for(variants.values())
    lines = [services.Line(sku=s, quantity=q, unit_satang=prices[variants[s].id].satang, promoted=prices[variants[s].id].discounted)
             for s, q in qty.items()]
    phone = None
    if data.phone.strip():
        try:
            phone = normalize_phone(data.phone)
        except HttpError:
            phone = None                                   # a half-typed phone must not block the preview
    try:
        ev = services.evaluate(data.code, lines, phone=phone)
    except CouponError:
        ratelimit.failed("coupon_fail_ip", ip)
        raise
    return {"code": ev.coupon.code, "label": ev.coupon.label, "subtotal_satang": ev.subtotal_satang,
            "discount_satang": ev.discount_satang, "goods_total_satang": ev.goods_total_satang}
