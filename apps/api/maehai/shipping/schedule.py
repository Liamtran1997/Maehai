"""When can an order be fulfilled? Cut-off at 13:00, no Sundays, no Thai public holidays."""
from datetime import date, datetime, timedelta

from django.conf import settings
from django.utils import timezone


def _working(d: date) -> bool:
    return d.weekday() not in settings.NO_FULFILLMENT_WEEKDAYS and d.isoformat() not in settings.NON_WORKING_DATES


def _local(now: datetime | None) -> datetime:
    return timezone.localtime(now or timezone.now())


def earliest_fulfillment_date(now: datetime | None = None) -> date:
    now = _local(now)
    d = now.date() + timedelta(days=1 if now.hour < settings.ORDER_CUTOFF_HOUR else 2)
    while not _working(d):
        d += timedelta(days=1)
    return d


def validate_fulfillment_date(d: date, now: datetime | None = None) -> str | None:
    """Returns a Thai error message, or None if the date is acceptable."""
    if d < earliest_fulfillment_date(now):
        return "สั่งก่อน 13:00 น. รับของได้วันถัดไป เลือกวันที่ใหม่"
    if not _working(d):
        return "วันที่เลือกร้านไม่มีรอบจัดส่ง (วันอาทิตย์และวันหยุดนักขัตฤกษ์)"
    return None
