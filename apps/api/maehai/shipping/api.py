from ninja import Router, Schema

from .models import ShippingMethod
from .schedule import earliest_fulfillment_date

router = Router(tags=["shipping"])


class ShippingMethodOut(Schema):
    code: str
    name: str
    kind: str
    description: str
    requires_address: bool
    fee_is_quoted: bool


class ScheduleOut(Schema):
    earliest_date: str
    cutoff_hour: int


@router.get("/methods", response=list[ShippingMethodOut])
def list_methods(request):
    return ShippingMethod.objects.filter(is_active=True)


@router.get("/schedule", response=ScheduleOut)
def schedule(request):
    from django.conf import settings

    return {"earliest_date": earliest_fulfillment_date().isoformat(), "cutoff_hour": settings.ORDER_CUTOFF_HOUR}
