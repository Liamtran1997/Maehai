from datetime import datetime

from ninja import Query, Router, Schema
from pydantic import Field

from maehai.core.auth import requires

from . import services

router = Router(tags=["admin-reports"])


class Period(Schema):
    revenue_satang: int
    paid_orders: int
    avg_order_satang: int


class DayOut(Schema):
    date: str
    revenue_satang: int


class TopProduct(Schema):
    name: str
    quantity: int


class ShipRevenue(Schema):
    name: str
    revenue_satang: int


class Todo(Schema):
    slips_to_check: int
    pending_quote: int
    waiting_payment: int
    to_pack: int
    low_stock: int = 0
    slips_to_receive: int = 0


class SummaryOut(Schema):
    days: int
    current: Period
    previous: Period
    orders_created: int
    daily: list[DayOut]
    top_products: list[TopProduct]
    by_shipping: list[ShipRevenue]
    todo: Todo


class SummaryQuery(Schema):
    days: int = Field(default=7, ge=1, le=90)


@router.get("/summary", response=SummaryOut, auth=requires("reports.view"))
def summary(request, params: Query[SummaryQuery]):
    return services.summary(params.days)


@router.get("/todo", response=Todo, auth=requires(None))
def todo(request):
    """Counts of things waiting for action. Visible to every staff member (no money figures)."""
    return services.todo()


class PromotionReportOut(Schema):
    id: int
    name: str
    label: str
    scope: str
    starts_at: datetime
    ends_at: datetime | None
    orders: int
    units: int
    revenue_satang: int
    discount_satang: int
    units_per_day: float
    units_per_day_before: float
    lift_percent: int | None


class CouponReportOut(Schema):
    id: int
    code: str
    name: str
    label: str
    uses: int
    cancelled: int
    orders: int
    revenue_satang: int
    discount_satang: int
    average_discount_satang: int
    free_shipping_orders: int


class CampaignsOut(Schema):
    days: int
    promotions: list[PromotionReportOut]
    coupons: list[CouponReportOut]


@router.get("/campaigns", response=CampaignsOut, auth=requires("reports.view"))
def campaigns(request, params: Query[SummaryQuery]):
    return services.campaign_report(params.days)
