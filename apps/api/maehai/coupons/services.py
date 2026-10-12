"""Decides whether a coupon applies to an order and how much it takes off. Used by the checkout preview AND by order
creation, so the discount a customer sees is the discount they get."""
from dataclasses import dataclass
from datetime import datetime

from django.utils import timezone
from ninja.errors import HttpError

from maehai.core.money import format_thb

from .models import CODE_RE, Coupon, CouponRedemption

MIN_PAYABLE_SATANG = 100   # goods must still cost at least 1 baht: PromptPay cannot charge 0


class CouponError(HttpError):
    """A coupon problem, in Thai, safe to show to the customer."""

    def __init__(self, message: str):
        super().__init__(422, message)


@dataclass(frozen=True)
class Line:
    """One order line as the coupon sees it."""
    sku: str
    quantity: int
    unit_satang: int          # after per-product promotion
    promoted: bool            # True if a product promotion already lowered this price

    @property
    def total(self) -> int:
        return self.unit_satang * self.quantity


@dataclass(frozen=True)
class Evaluation:
    coupon: Coupon
    discount_satang: int
    subtotal_satang: int
    goods_total_satang: int   # subtotal - discount
    shipping_waived: bool = False   # a free-shipping code: the delivery fee is not charged


def normalize(code: str) -> str:
    return (code or "").strip().upper()


NOT_FOUND = "ไม่พบโค้ดนี้หรือหมดอายุแล้ว"   # one message for unknown, switched off, not started, ended: no hints for guessers


def _active_uses(coupon: Coupon, phone: str | None = None) -> int:
    qs = CouponRedemption.objects.filter(coupon=coupon, released_at__isnull=True)
    return (qs.filter(phone=phone) if phone else qs).count()


def evaluate(code: str, lines: list[Line], *, phone: str | None = None, at: datetime | None = None,
             lock: bool = False, shipping_applies: bool = True) -> Evaluation:
    """Raises CouponError with a customer-facing message when the code cannot be used.
    lock=True takes a row lock on the coupon so two simultaneous orders cannot both take its last use (call inside a transaction)."""
    code = normalize(code)
    if not CODE_RE.match(code):
        raise CouponError(NOT_FOUND)
    qs = Coupon.objects.select_for_update() if lock else Coupon.objects
    coupon = qs.filter(code=code).first()
    if coupon is None or not coupon.is_live(at or timezone.now()):
        raise CouponError(NOT_FOUND)

    if coupon.usage_limit is not None and _active_uses(coupon) >= coupon.usage_limit:
        raise CouponError("โค้ดนี้ถูกใช้ครบจำนวนแล้ว")
    if phone and coupon.per_phone_limit is not None and _active_uses(coupon, phone) >= coupon.per_phone_limit:
        raise CouponError("เบอร์โทรนี้ใช้โค้ดนี้ครบสิทธิ์แล้ว")

    subtotal = sum(l.total for l in lines)
    eligible = sum(l.total for l in lines if not (coupon.exclude_discounted_items and l.promoted))
    if eligible <= 0:
        raise CouponError("โค้ดนี้ใช้กับสินค้าที่ลดราคาอยู่แล้วไม่ได้")
    if eligible < coupon.min_subtotal_satang:
        short = coupon.min_subtotal_satang - eligible
        raise CouponError(f"ซื้อครบ {format_thb(coupon.min_subtotal_satang)} เพื่อใช้โค้ดนี้ (ขาดอีก {format_thb(short)})")

    if coupon.kind == Coupon.Kind.FREE_SHIPPING:
        if not shipping_applies:
            raise CouponError("โค้ดส่งฟรีใช้กับการจัดส่งถึงที่หรือฝากขนส่งเท่านั้น รับที่ร้านไม่มีค่าจัดส่งอยู่แล้ว")
        return Evaluation(coupon, 0, subtotal, subtotal, shipping_waived=True)

    if coupon.kind == Coupon.Kind.PERCENT:
        off = (eligible * coupon.value + 50) // 100
        if coupon.max_discount_satang:
            off = min(off, coupon.max_discount_satang)
    else:
        off = min(coupon.value, eligible)
    off = min(off, subtotal - MIN_PAYABLE_SATANG)       # never make the goods free
    if off <= 0:
        raise CouponError("โค้ดนี้ใช้กับยอดนี้ไม่ได้")
    return Evaluation(coupon, off, subtotal, subtotal - off)


def redeem(coupon: Coupon, order, phone: str, discount_satang: int) -> CouponRedemption:
    return CouponRedemption.objects.create(coupon=coupon, order=order, phone=phone, discount_satang=discount_satang)


def release_for_order(order) -> None:
    """A cancelled order gives its coupon use back."""
    CouponRedemption.objects.filter(order=order, released_at__isnull=True).update(released_at=timezone.now())
