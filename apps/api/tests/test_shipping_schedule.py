from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from maehai.shipping.schedule import earliest_fulfillment_date, validate_fulfillment_date

BKK = ZoneInfo("Asia/Bangkok")
at = lambda y, m, d, h, mi=0: datetime(y, m, d, h, mi, tzinfo=BKK)


@pytest.mark.parametrize("now, expected", [
    (at(2026, 10, 12, 12, 59), date(2026, 10, 13)),   # Mon before cut-off -> Tue
    (at(2026, 10, 12, 13, 0), date(2026, 10, 14)),    # Mon at cut-off -> Wed
    (at(2026, 10, 9, 10, 0), date(2026, 10, 10)),     # Fri morning -> Sat (Saturday is a working day)
    (at(2026, 10, 10, 10, 0), date(2026, 10, 12)),    # Sat morning -> Sunday skipped -> Mon
    (at(2026, 10, 10, 14, 0), date(2026, 10, 12)),    # Sat afternoon -> Mon (Sunday skipped)
])
def test_earliest_date(now, expected):
    assert earliest_fulfillment_date(now) == expected


def test_holidays_are_skipped(settings):
    settings.NON_WORKING_DATES = ["2026-10-13"]
    assert earliest_fulfillment_date(at(2026, 10, 12, 9)) == date(2026, 10, 14)


def test_validate_messages():
    now = at(2026, 10, 12, 9)
    assert validate_fulfillment_date(date(2026, 10, 13), now) is None
    assert "13:00" in validate_fulfillment_date(date(2026, 10, 12), now)
    assert "วันอาทิตย์" in validate_fulfillment_date(date(2026, 10, 18), now)
