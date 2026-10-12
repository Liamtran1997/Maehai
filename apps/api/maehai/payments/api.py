from ninja import File, Router
from ninja.files import UploadedFile

from maehai.core import ratelimit
from maehai.orders.access import order_by_token
from maehai.orders.schemas import PaymentOut
from maehai.orders.serializers import payment_out

from . import services

router = Router(tags=["payments"])


@router.post("/{number}/charge", response=PaymentOut)
def charge(request, number: str, token: str):
    """Get (or create) the PromptPay QR for this order."""
    order = order_by_token(request, number, token)
    ratelimit.hit("charge_order", order.number)
    return payment_out(request, services.start_payment(order), include_qr=True)


@router.post("/{number}/slip", response=PaymentOut)
def upload_slip(request, number: str, token: str, slip: File[UploadedFile]):
    order = order_by_token(request, number, token)
    ratelimit.hit("slip_order", order.number)
    ratelimit.hit("slip_ip", ratelimit.client_ip(request))
    payment = services.start_payment(order)
    return payment_out(request, services.submit_slip(payment, slip), include_qr=False)
