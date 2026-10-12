"""Customer-facing order API. No login: an order is reached with its secret token (or number + phone to get the token)."""
from ninja import Router

from maehai.core import ratelimit
from maehai.coupons.services import CouponError

from . import services
from .access import order_by_token
from .models import Order
from .schemas import LookupIn, OrderIn, OrderOut, TokenOut
from .serializers import order_out

router = Router(tags=["orders"])


def _load(number: str) -> Order:
    return Order.objects.select_related("shipping_method", "fulfillment_branch").prefetch_related("items", "events", "payments").get(number=number)


@router.post("", response={201: OrderOut})
def place_order(request, data: OrderIn):
    ratelimit.hit("order_create_ip", ratelimit.client_ip(request))
    ratelimit.hit("order_create_phone", services.normalize_phone(data.phone))
    ip = ratelimit.client_ip(request)
    if data.coupon_code.strip():
        ratelimit.blocked("coupon_fail_ip", ip)   # stops anyone from guessing codes through checkout
    try:
        order = _create(data)
    except CouponError:
        ratelimit.failed("coupon_fail_ip", ip)
        raise
    return 201, order_out(request, _load(order.number))


def _create(data):
    order = services.create_order(
        items=[(i.sku, i.quantity) for i in data.items], customer_name=data.customer_name, phone=data.phone,
        shipping_code=data.shipping_method, requested_date=data.requested_date,
        address=data.address.dict(), note=data.note, coupon_code=data.coupon_code,
    )
    return order


@router.post("/lookup", response=TokenOut)
def lookup(request, data: LookupIn):
    """Find an order by number + the phone used to place it. Same 404 for any mismatch, and guessing is throttled."""
    from ninja.errors import HttpError

    ip = ratelimit.client_ip(request)
    number = data.number.strip().upper()
    ratelimit.hit("lookup_ip", ip)
    ratelimit.blocked("lookup_fail_ip", ip)
    ratelimit.blocked("lookup_fail_order", number)
    try:
        phone = services.normalize_phone(data.phone)
        order = Order.objects.filter(number=number, phone=phone).first()
        if order is None:
            raise HttpError(404, "ไม่พบคำสั่งซื้อ ตรวจสอบเลขที่และเบอร์โทรอีกครั้ง")
    except HttpError:
        ratelimit.failed("lookup_fail_ip", ip)
        ratelimit.failed("lookup_fail_order", number)
        raise
    ratelimit.forgive("lookup_fail_order", number)
    return {"number": order.number, "token": order.public_token}


# Declared after /lookup so the literal path wins over /{number}.
@router.get("/{number}", response=OrderOut)
def get_order(request, number: str, token: str):
    return order_out(request, order_by_token(request, number, token))
