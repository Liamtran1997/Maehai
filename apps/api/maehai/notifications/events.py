"""Turns order and payment changes into queued LINE messages. Call inside the transaction that made the change."""
from django.conf import settings

from . import texts
from .models import Outbox


def _queue(audience: str, recipient: str, kind: str, text: str, order) -> None:
    Outbox.objects.create(audience=audience, recipient=recipient, kind=kind, text=text, order=order)


def _staff(kind: str, text: str, order) -> None:
    for rid in settings.LINE_STAFF_IDS:
        _queue("staff", rid, kind, text, order)


def _customer(kind: str, text: str, order) -> None:
    if order.line_user_id:  # the customer has not connected LINE: nothing to send, the order page still shows status
        _queue("customer", order.line_user_id, kind, text, order)


def order_created(order) -> None:
    _staff("order_created", texts.staff_new_order(order), order)


def slip_submitted(order, amount_satang: int) -> None:
    _staff("slip_submitted", texts.staff_slip(order, amount_satang), order)


def fee_quoted(order) -> None:
    _customer("fee_quoted", texts.customer_fee_quoted(order), order)


def payment_confirmed(order) -> None:
    _customer("paid", texts.customer_paid(order), order)


def slip_rejected(order, reason: str) -> None:
    _customer("slip_rejected", texts.customer_slip_rejected(order, reason), order)


def shipped(order) -> None:
    _customer("shipped", texts.customer_shipped(order), order)


def cancelled(order) -> None:
    _customer("cancelled", texts.customer_cancelled(order), order)


def low_stock(variant, branch, available: int) -> None:
    _staff("low_stock", texts.staff_low_stock(variant, branch, available), None)


def restocked(variant, line_user_id: str) -> None:
    _queue("customer", line_user_id, "restocked", texts.customer_restocked(variant), None)
