"""Staff-only coupon management."""
from datetime import datetime

from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from ninja import Field, Router, Schema
from ninja.errors import HttpError

from maehai.core.auth import requires
from maehai.core.models import audit

from .models import CODE_RE, Coupon, CouponRedemption

router = Router(tags=["admin-coupons"])


class CouponIn(Schema):
    code: str
    name: str = Field(min_length=1, max_length=100)
    kind: str                                   # percent | amount
    value: int = Field(gt=0)                    # percent, or satang off the order
    max_discount_satang: int | None = Field(default=None, gt=0)
    min_subtotal_satang: int = Field(default=0, ge=0)
    exclude_discounted_items: bool = False
    usage_limit: int | None = Field(default=None, gt=0)
    per_phone_limit: int | None = Field(default=1, gt=0)
    starts_at: datetime
    ends_at: datetime | None = None
    is_active: bool = True


class CouponOut(Schema):
    id: int
    code: str
    name: str
    kind: str
    value: int
    label: str
    max_discount_satang: int | None
    min_subtotal_satang: int
    exclude_discounted_items: bool
    usage_limit: int | None
    per_phone_limit: int | None
    starts_at: datetime
    ends_at: datetime | None
    is_active: bool
    used_count: int
    remaining: int | None
    discount_given_satang: int
    state: str                                  # scheduled | running | ended | off | exhausted


class RedemptionOut(Schema):
    order_number: str
    customer_name: str
    phone: str
    discount_satang: int
    created_at: datetime
    released: bool


def _out(c: Coupon, stats: dict | None = None) -> dict:
    s = stats if stats is not None else CouponRedemption.objects.filter(coupon=c, released_at__isnull=True).aggregate(n=Count("id"), d=Sum("discount_satang"))
    used, given = s["n"] or 0, s["d"] or 0
    now = timezone.now()
    if not c.is_active:
        state = "off"
    elif c.starts_at > now:
        state = "scheduled"
    elif c.ends_at and c.ends_at <= now:
        state = "ended"
    elif c.usage_limit is not None and used >= c.usage_limit:
        state = "exhausted"
    else:
        state = "running"
    return {"id": c.id, "code": c.code, "name": c.name, "kind": c.kind, "value": c.value, "label": c.label,
            "max_discount_satang": c.max_discount_satang, "min_subtotal_satang": c.min_subtotal_satang,
            "exclude_discounted_items": c.exclude_discounted_items, "usage_limit": c.usage_limit,
            "per_phone_limit": c.per_phone_limit, "starts_at": c.starts_at, "ends_at": c.ends_at, "is_active": c.is_active,
            "used_count": used, "remaining": None if c.usage_limit is None else max(0, c.usage_limit - used),
            "discount_given_satang": given, "state": state}


def _validate(data: CouponIn) -> str:
    code = data.code.strip().upper()
    if not CODE_RE.match(code):
        raise HttpError(422, "โค้ดใช้ตัวอักษร A-Z ตัวเลข และขีดกลาง ยาว 2 ถึง 24 ตัว")
    if data.kind not in Coupon.Kind.values:
        raise HttpError(422, "ประเภทส่วนลดไม่ถูกต้อง")
    if data.kind == Coupon.Kind.PERCENT and not 1 <= data.value <= 90:
        raise HttpError(422, "ลดได้ 1 ถึง 90 เปอร์เซ็นต์")
    if data.kind == Coupon.Kind.AMOUNT and data.max_discount_satang is not None:
        raise HttpError(422, "เพดานส่วนลดใช้กับโค้ดแบบเปอร์เซ็นต์เท่านั้น")
    if data.ends_at and data.ends_at <= data.starts_at:
        raise HttpError(422, "วันสิ้นสุดต้องอยู่หลังวันเริ่ม")
    return code


@router.get("/coupons", response=list[CouponOut], auth=requires("coupons.view"))
def list_coupons(request):
    stats = {r["coupon_id"]: r for r in CouponRedemption.objects.filter(released_at__isnull=True)
             .values("coupon_id").annotate(n=Count("id"), d=Sum("discount_satang")).order_by("coupon_id")}
    return [_out(c, stats.get(c.id, {"n": 0, "d": 0})) for c in Coupon.objects.order_by("-created_at", "-id")]


@router.post("/coupons", response={201: CouponOut}, auth=requires("pricing.manage"))
def create_coupon(request, data: CouponIn):
    code = _validate(data)
    if Coupon.objects.filter(code=code).exists():
        raise HttpError(409, "โค้ดนี้มีอยู่แล้ว")
    fields = data.dict(exclude={"code"})
    c = Coupon.objects.create(code=code, created_by=request.user.get_username(), **fields)
    audit(request, "coupon.create", c.code, c.label)
    return 201, _out(c)


@router.put("/coupons/{coupon_id}", response=CouponOut, auth=requires("pricing.manage"))
def update_coupon(request, coupon_id: int, data: CouponIn):
    c = get_object_or_404(Coupon, pk=coupon_id)
    code = _validate(data)
    if code != c.code:
        if c.redemptions.exists():
            raise HttpError(409, "โค้ดนี้ถูกใช้แล้ว เปลี่ยนตัวโค้ดไม่ได้ ให้สร้างโค้ดใหม่แทน")
        if Coupon.objects.filter(code=code).exists():
            raise HttpError(409, "โค้ดนี้มีอยู่แล้ว")
    for k, v in data.dict(exclude={"code"}).items():
        setattr(c, k, v)
    c.code = code
    c.save()
    audit(request, "coupon.update", c.code, c.label)
    return _out(c)


@router.post("/coupons/{coupon_id}/end", response=CouponOut, auth=requires("pricing.manage"))
def end_coupon(request, coupon_id: int):
    """Stop the code now. Orders that already used it keep their discount."""
    c = get_object_or_404(Coupon, pk=coupon_id)
    now = timezone.now()
    if c.starts_at > now:
        c.is_active = False
    elif not c.ends_at or c.ends_at > now:
        c.ends_at = now
    c.save()
    audit(request, "coupon.end", c.code)
    return _out(c)


@router.delete("/coupons/{coupon_id}", response={204: None}, auth=requires("pricing.manage"))
def delete_coupon(request, coupon_id: int):
    c = get_object_or_404(Coupon, pk=coupon_id)
    if c.redemptions.exists():
        raise HttpError(409, "โค้ดนี้ถูกใช้แล้ว ลบไม่ได้ ใช้ “ปิดโค้ด” แทนเพื่อเก็บประวัติ")
    audit(request, "coupon.delete", c.code)
    c.delete()
    return 204, None


@router.get("/coupons/{coupon_id}/redemptions", response=list[RedemptionOut], auth=requires("coupons.view"))
def redemptions(request, coupon_id: int):
    get_object_or_404(Coupon, pk=coupon_id)
    rows = CouponRedemption.objects.filter(coupon_id=coupon_id).select_related("order").order_by("-id")[:200]
    return [{"order_number": r.order.number, "customer_name": r.order.customer_name, "phone": r.phone,
             "discount_satang": r.discount_satang, "created_at": r.created_at, "released": r.released_at is not None} for r in rows]

