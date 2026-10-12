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
