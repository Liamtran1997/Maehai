"""Staff-only order management for the back office."""
from django.db.models import Q
from django.shortcuts import get_object_or_404
from ninja import Router
from ninja.pagination import LimitOffsetPagination, paginate

from maehai.core.auth import staff_auth
from maehai.payments import services as payment_services
from maehai.payments.models import Payment

from . import services
from .models import Order
from .schemas import BranchIn, FeeIn, OrderOut, OrderSummaryOut, PaymentOut, RejectIn, StatusIn
from .serializers import order_out, payment_out

router = Router(tags=["admin-orders"], auth=staff_auth)


def _qs():
    return Order.objects.select_related("shipping_method", "fulfillment_branch").prefetch_related("items", "events", "payments")


@router.get("/orders", response=list[OrderSummaryOut])
@paginate(LimitOffsetPagination)
def list_orders(request, status: str | None = None, q: str | None = None):
    qs = Order.objects.select_related("shipping_method")
    if status:
        qs = qs.filter(status=status)
    if q:
        qs = qs.filter(Q(number__icontains=q) | Q(customer_name__icontains=q) | Q(phone__icontains=q.replace("-", "")))
    return [{**order_out_summary(o)} for o in qs]


def order_out_summary(o: Order) -> dict:
    from .models import OrderStatus

    return {"number": o.number, "status": o.status, "status_label": OrderStatus(o.status).label,
            "customer_name": o.customer_name, "phone": o.phone, "shipping_method": o.shipping_method,
            "requested_date": o.requested_date, "total_satang": o.total_satang, "created_at": o.created_at}


@router.get("/orders/{number}", response=OrderOut)
def get_order(request, number: str):
    return order_out(request, get_object_or_404(_qs(), number=number), staff=True)


@router.post("/orders/{number}/fee", response=OrderOut)
def set_fee(request, number: str, data: FeeIn):
    order = services.quote_fee(get_object_or_404(Order, number=number), data.fee_satang, actor=request.user.get_username())
    return order_out(request, _qs().get(pk=order.pk), staff=True)


@router.post("/orders/{number}/status", response=OrderOut)
def set_status(request, number: str, data: StatusIn):
    order = services.staff_set_status(get_object_or_404(Order, number=number), data.status,
                                      actor=request.user.get_username(), tracking_ref=data.tracking_ref)
    return order_out(request, _qs().get(pk=order.pk), staff=True)


@router.post("/payments/{payment_id}/confirm", response=PaymentOut)
def confirm_payment(request, payment_id: int):
    p = payment_services.confirm(get_object_or_404(Payment, pk=payment_id), actor=request.user.get_username())
    return payment_out(request, p, include_qr=False)


@router.post("/payments/{payment_id}/reject", response=PaymentOut)
def reject_payment(request, payment_id: int, data: RejectIn):
    p = payment_services.reject(get_object_or_404(Payment, pk=payment_id), actor=request.user.get_username(), reason=data.reason)
    return payment_out(request, p, include_qr=False)


@router.post("/orders/{number}/branch", response=OrderOut)
def set_branch(request, number: str, data: BranchIn):
    """Choose which branch's stock fills a delivery order. Pickup orders always use the branch the customer picked."""
    from ninja.errors import HttpError

    from maehai.inventory import services as stock
    from maehai.inventory.models import Branch
    from .models import OrderStatus

    order = get_object_or_404(Order, number=number)
    if order.shipping_method.branch_id:
        raise HttpError(409, "ออเดอร์รับที่ร้านเปลี่ยนสาขาไม่ได้")
    if order.status not in (OrderStatus.PENDING_QUOTE, OrderStatus.WAITING_PAYMENT, OrderStatus.PAID, OrderStatus.PACKING):
        raise HttpError(409, "คำสั่งซื้อนี้ปิดแล้ว")
    branch = get_object_or_404(Branch, code=data.branch, is_active=True)
    stock.reassign_branch(order, branch)
    services.log(order, "branch", f"จัดจากสาขา {branch.name}", actor=request.user.get_username())
    return order_out(request, _qs().get(pk=order.pk), staff=True)
