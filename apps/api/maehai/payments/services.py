from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.module_loading import import_string
from ninja.errors import HttpError
from promptpay import qrcode

from maehai.notifications import events as notify
from maehai.orders import services as order_services
from maehai.orders.models import Order, OrderStatus

from .models import Payment, PaymentStatus

ALLOWED_SLIP_TYPES = {"image/jpeg", "image/png", "image/webp"}


def expire_pending(order: Order) -> None:
    order.payments.filter(status=PaymentStatus.PENDING).update(status=PaymentStatus.EXPIRED)


def _is_live(p: Payment) -> bool:
    """A submitted slip stays live until staff decide, however long that takes. An unpaid QR lives 15 minutes."""
    return p.status == PaymentStatus.SLIP_SUBMITTED or (p.status == PaymentStatus.PENDING and p.expires_at > timezone.now())


@transaction.atomic
def start_payment(order: Order) -> Payment:
    """Get the live QR for an order, or make a new one. Order must be waiting for payment with a known total."""
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.status != OrderStatus.WAITING_PAYMENT or order.total_satang is None:
        raise HttpError(409, "คำสั่งซื้อนี้ยังชำระเงินไม่ได้")
    if not settings.PROMPTPAY_ID:
        raise HttpError(503, "ร้านยังไม่ได้ตั้งค่า PromptPay")

    for p in order.payments.filter(status__in=[PaymentStatus.PENDING, PaymentStatus.SLIP_SUBMITTED]):
        if _is_live(p) and p.amount_satang == order.total_satang:
            return p
        if p.status == PaymentStatus.PENDING:
            p.status = PaymentStatus.EXPIRED
            p.save(update_fields=["status"])

    return Payment.objects.create(
        order=order,
        amount_satang=order.total_satang,
        qr_payload=qrcode.generate_payload(settings.PROMPTPAY_ID, order.total_satang / 100),
        expires_at=timezone.now() + timedelta(minutes=settings.PAYMENT_WINDOW_MINUTES),
    )


def _check_slip(file) -> None:
    if file.content_type not in ALLOWED_SLIP_TYPES:
        raise HttpError(422, "รองรับเฉพาะรูป JPG, PNG หรือ WebP")
    if file.size > settings.SLIP_MAX_BYTES:
        raise HttpError(422, "ไฟล์ใหญ่เกิน 5 MB")


@transaction.atomic
def submit_slip(payment: Payment, file) -> Payment:
    _check_slip(file)
    payment = Payment.objects.select_for_update().select_related("order").get(pk=payment.pk)
    if payment.status not in (PaymentStatus.PENDING, PaymentStatus.SLIP_SUBMITTED):
        raise HttpError(409, "การชำระเงินนี้ปิดแล้ว")
    payment.slip = file
    payment.slip_submitted_at = timezone.now()
    payment.status = PaymentStatus.SLIP_SUBMITTED
    payment.save()
    order_services.log(payment.order, "slip_submitted", f"฿{payment.amount_satang / 100:,.2f}")

    result = import_string(settings.SLIP_VERIFIER)().verify(payment)
    if result.ok is True:
        return confirm(payment, actor="slip-verifier")
    if result.ok is False:
        return reject(payment, actor="slip-verifier", reason=result.detail or "สลิปไม่ผ่านการตรวจสอบ")
    notify.slip_submitted(payment.order, payment.amount_satang)  # a person has to look at it
    return payment


@transaction.atomic
def confirm(payment: Payment, actor: str) -> Payment:
    """Idempotent. Marks the payment confirmed and the order paid."""
    payment = Payment.objects.select_for_update().select_related("order").get(pk=payment.pk)
    if payment.status == PaymentStatus.CONFIRMED:
        return payment
    if payment.status in (PaymentStatus.REJECTED, PaymentStatus.EXPIRED) and payment.slip_submitted_at is None:
        raise HttpError(409, "ยังไม่มีสลิปสำหรับรายการนี้")
    order = Order.objects.select_for_update().get(pk=payment.order_id)
    if order.status != OrderStatus.WAITING_PAYMENT:
        raise HttpError(409, "สถานะคำสั่งซื้อไม่ตรง ยืนยันการชำระไม่ได้")
    if payment.amount_satang != order.total_satang:
        raise HttpError(409, "ยอดชำระไม่ตรงกับยอดคำสั่งซื้อ")
    payment.status = PaymentStatus.CONFIRMED
    payment.confirmed_at = timezone.now()
    payment.decided_by = actor
    payment.save()
    order_services.change_status(order, OrderStatus.PAID, actor=actor, detail="ยืนยันการชำระเงิน", system=True)
    notify.payment_confirmed(order)
    return payment


@transaction.atomic
def reject(payment: Payment, actor: str, reason: str) -> Payment:
    payment = Payment.objects.select_for_update().select_related("order").get(pk=payment.pk)
    if payment.status != PaymentStatus.SLIP_SUBMITTED:
        raise HttpError(409, "รายการนี้ไม่ได้รอตรวจสลิป")
    payment.status = PaymentStatus.REJECTED
    payment.decided_by = actor
    payment.reject_reason = reason[:200]
    payment.save()
    order_services.log(payment.order, "payment_rejected", reason[:200], actor=actor)
    notify.slip_rejected(payment.order, reason[:200])
    return payment
