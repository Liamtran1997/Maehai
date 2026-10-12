from urllib.parse import quote

from django.conf import settings
from django.utils import timezone

from maehai.payments.models import PaymentStatus

from .models import Order, OrderStatus


def payment_out(request, p, *, include_qr: bool, staff: bool = False) -> dict | None:
    if p is None:
        return None
    live = p.status == PaymentStatus.PENDING and p.expires_at > timezone.now()
    return {
        "id": p.id, "status": p.status, "amount_satang": p.amount_satang, "expires_at": p.expires_at,
        "qr_payload": p.qr_payload if (include_qr and live) else None,
        # Slips show bank details: only staff get a link, and it goes through a login-protected endpoint, never /media.
        "slip_url": request.build_absolute_uri(f"/api/admin/payments/{p.id}/slip") if (staff and p.slip) else None,
        "reject_reason": p.reject_reason,
    }


def line_link_url(o: Order) -> str:
    """Opens LINE with a prefilled message to the shop's OA. Sending it connects this order to the customer's LINE."""
    text = f"{o.number} รหัส {o.line_link_code}"
    return f"https://line.me/R/oaMessage/{settings.LINE_OA_ID}/?{quote(text)}"


def order_out(request, o: Order, *, staff: bool = False, can_see_slips: bool = True) -> dict:
    payments = list(o.payments.all())
    latest = payments[0] if payments else None  # Payment.Meta.ordering is newest first
    if latest and latest.status == PaymentStatus.PENDING and latest.expires_at <= timezone.now():
        latest.status = PaymentStatus.EXPIRED  # display only; the row is refreshed on the next charge
    return {
        "number": o.number, "token": o.public_token, "status": o.status,
        "status_label": OrderStatus(o.status).label, "customer_name": o.customer_name, "phone": o.phone,
        "shipping_method": o.shipping_method, "requested_date": o.requested_date,
        "address_line": o.address_line, "subdistrict": o.subdistrict, "district": o.district,
        "province": o.province, "postal_code": o.postal_code, "note": o.note,
        "items": [{"sku": i.sku, "product_name": i.product_name, "variant_label": i.variant_label,
                   "unit_price_satang": i.unit_price_satang, "quantity": i.quantity,
                   "list_price_satang": i.list_price_satang, "promotion_name": i.promotion_name,
                   "line_total_satang": i.line_total_satang} for i in o.items.all()],
        "subtotal_satang": o.subtotal_satang, "shipping_fee_satang": o.shipping_fee_satang,
        "discount_satang": sum(i.line_discount_satang for i in o.items.all()),
        "coupon_code": o.coupon_code, "coupon_discount_satang": o.coupon_discount_satang,
        "vat_satang": o.vat_satang, "total_satang": o.total_satang, "tracking_ref": o.tracking_ref,
        "created_at": o.created_at,
        "events": [{"created_at": e.created_at, "kind": e.kind, "detail": e.detail} for e in o.events.all()],
        "payment": payment_out(request, latest, include_qr=not staff, staff=staff and can_see_slips),
        "fulfillment_branch": o.fulfillment_branch,
        "line_linked": bool(o.line_user_id),
        "line_link_url": None if o.line_user_id or not settings.LINE_OA_ID else line_link_url(o),
    }
