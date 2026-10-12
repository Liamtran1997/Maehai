"""Sales numbers for the back-office dashboard.

Everything is counted on a cash basis: a sale belongs to the day its payment was CONFIRMED,
in Asia/Bangkok time. Cancelled or unpaid orders never count as sales.
"""
from datetime import date, datetime, timedelta

from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from maehai.inventory.services import low_stock_count
from maehai.orders.models import Order, OrderItem, OrderStatus
from maehai.payments.models import Payment, PaymentStatus


def _window(days: int, end: date | None = None) -> tuple[datetime, datetime, date]:
    """[start, end) in local time covering the last `days` days including today."""
    tz = timezone.get_current_timezone()
    last = end or timezone.localdate()
    first = last - timedelta(days=days - 1)
    return (datetime.combine(first, datetime.min.time(), tz),
            datetime.combine(last + timedelta(days=1), datetime.min.time(), tz), first)


def _period(start: datetime, end: datetime) -> dict:
    paid = Payment.objects.filter(status=PaymentStatus.CONFIRMED, confirmed_at__gte=start, confirmed_at__lt=end)
    revenue = paid.aggregate(s=Sum("amount_satang"))["s"] or 0
    n = paid.count()
    return {"revenue_satang": revenue, "paid_orders": n, "avg_order_satang": revenue // n if n else 0}


def summary(days: int = 7) -> dict:
    start, end, first = _window(days)
    prev_start, prev_end = start - timedelta(days=days), start
    cur, prev = _period(start, end), _period(prev_start, prev_end)

    paid = Payment.objects.filter(status=PaymentStatus.CONFIRMED, confirmed_at__gte=start, confirmed_at__lt=end)
    per_day = {r["d"]: r["s"] for r in paid.annotate(d=TruncDate("confirmed_at")).values("d").annotate(s=Sum("amount_satang"))}
    daily = [{"date": (first + timedelta(days=i)).isoformat(), "revenue_satang": per_day.get(first + timedelta(days=i), 0)}
             for i in range(days)]

    order_ids = paid.values("order_id")
    top = (OrderItem.objects.filter(order_id__in=order_ids).values("product_name")
           .annotate(quantity=Sum("quantity")).order_by("-quantity", "product_name")[:5])
    by_ship = (Payment.objects.filter(pk__in=paid.values("pk")).values(name=_ship_name())
               .annotate(revenue_satang=Sum("amount_satang")).order_by("-revenue_satang"))

    return {
        "days": days, "current": cur, "previous": prev,
        "orders_created": Order.objects.filter(created_at__gte=start, created_at__lt=end).exclude(status=OrderStatus.CANCELLED).count(),
        "daily": daily,
        "top_products": [{"name": r["product_name"], "quantity": r["quantity"]} for r in top],
        "by_shipping": [{"name": r["name"], "revenue_satang": r["revenue_satang"]} for r in by_ship],
        "todo": todo(),
    }


def _ship_name():
    from django.db.models import F

    return F("order__shipping_method__name")


def todo() -> dict:
    """What staff need to act on right now."""
    by_status = dict(Order.objects.values_list("status").annotate(n=Count("id")))
    return {
        "slips_to_check": Payment.objects.filter(status=PaymentStatus.SLIP_SUBMITTED).count(),
        "pending_quote": by_status.get(OrderStatus.PENDING_QUOTE, 0),
        "waiting_payment": by_status.get(OrderStatus.WAITING_PAYMENT, 0),
        "to_pack": by_status.get(OrderStatus.PAID, 0),
        "low_stock": low_stock_count(),
    }


# ---------------------------------------------------------------- campaign effectiveness
COUNTED_STATUSES = ("paid", "packing", "shipped", "done")   # money is in: paid, and not cancelled since


def _variant_ids(promo) -> list[int]:
    from maehai.catalog.models import Promotion, ProductVariant

    qs = ProductVariant.objects.filter(is_active=True)
    if promo.scope == Promotion.Scope.PRODUCTS:
        qs = qs.filter(product__in=promo.products.all())
    elif promo.scope == Promotion.Scope.CATEGORIES:
        qs = qs.filter(product__category__in=promo.categories.all())
    return list(qs.values_list("id", flat=True))


def _units(variant_ids, start, end) -> int:
    from maehai.orders.models import OrderItem

    return OrderItem.objects.filter(variant_id__in=variant_ids, order__status__in=COUNTED_STATUSES,
                                    order__created_at__gte=start, order__created_at__lt=end).aggregate(q=Sum("quantity"))["q"] or 0


def campaign_report(days: int = 30) -> dict:
    """How well each promotion and coupon did in the last `days` days.

    Promotions: units sold during the promotion per day, against the same number of days just before it started,
    for the same products. The change between the two is the lift. Only paid orders count.
    Coupons: uses, goods sold with them, discount given, and cancelled uses (which give the use back).
    """
    from maehai.catalog.models import Promotion
    from maehai.coupons.models import Coupon, CouponRedemption
    from maehai.orders.models import Order, OrderItem

    now = timezone.now()
    start, end, _ = _window(days)
    promotions = []
    for promo in Promotion.objects.prefetch_related("products", "categories").order_by("-starts_at"):
        p_from = max(promo.starts_at, start)
        p_to = min(promo.ends_at or now, end, now)
        if p_to <= p_from:
            continue                                   # not running in this window
        items = OrderItem.objects.filter(promotion=promo, order__status__in=COUNTED_STATUSES,
                                         order__created_at__gte=start, order__created_at__lt=end)
        rows = list(items.values_list("unit_price_satang", "list_price_satang", "quantity", "order_id"))
        orders = len({r[3] for r in rows})
        units = sum(r[2] for r in rows)
        revenue = sum(r[0] * r[2] for r in rows)
        discount = sum(((r[1] or r[0]) - r[0]) * r[2] for r in rows)

        length = p_to - p_from
        ids = _variant_ids(promo)
        per_day = _units(ids, p_from, p_to) / (length.total_seconds() / 86400)
        before = _units(ids, p_from - length, p_from) / (length.total_seconds() / 86400)
        promotions.append({
            "id": promo.id, "name": promo.name, "label": promo.label, "scope": promo.scope,
            "starts_at": promo.starts_at, "ends_at": promo.ends_at, "orders": orders, "units": units,
            "revenue_satang": revenue, "discount_satang": discount,
            "units_per_day": round(per_day, 2), "units_per_day_before": round(before, 2),
            "lift_percent": round((per_day - before) / before * 100) if before > 0 else None,
        })

    coupons = []
    for coupon in Coupon.objects.order_by("-created_at"):
        reds = CouponRedemption.objects.filter(coupon=coupon, created_at__gte=start, created_at__lt=end)
        if not reds.exists():
            continue
        active = reds.filter(released_at__isnull=True)
        counted = Order.objects.filter(coupon_redemption__in=active, status__in=COUNTED_STATUSES)
        goods = [(o.subtotal_satang, o.coupon_discount_satang, o.shipping_waived) for o in counted]
        discount = sum(g[1] for g in goods)
        coupons.append({
            "id": coupon.id, "code": coupon.code, "name": coupon.name, "label": coupon.label,
            "uses": active.count(), "cancelled": reds.filter(released_at__isnull=False).count(),
            "orders": len(goods), "revenue_satang": sum(g[0] - g[1] for g in goods),
            "discount_satang": discount, "average_discount_satang": discount // len(goods) if goods else 0,
            "free_shipping_orders": sum(1 for g in goods if g[2]),
        })
    return {"days": days, "promotions": promotions, "coupons": coupons}
