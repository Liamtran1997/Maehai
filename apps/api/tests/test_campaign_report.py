from datetime import timedelta

import pytest
from django.utils import timezone

from maehai.catalog.models import Product, Promotion
from maehai.coupons.models import Coupon
from maehai.orders.models import Order, OrderItem
from tests.test_reports import paid_order

pytestmark = pytest.mark.django_db
PEPPER_2 = "moo-yo-black-pepper-2"


def now():
    return timezone.now()


def report(staff, days=30):
    return staff.get("/api/admin/reports/campaigns", {"days": days}).json()


def test_lift_compares_the_promotion_with_the_days_just_before_it(staff_client, place, client, seeded):
    # 10% on the whole pepper product, running for the last 3 days
    promo = Promotion.objects.create(name="ลดสงกรานต์", kind="percent", value=10, scope="products",
                                     starts_at=now() - timedelta(days=3), created_by="owner")
    promo.products.add(Product.objects.get(slug="moo-yo-black-pepper"))
    # the 3 days before the promotion: 1 unit sold, then the promotion: 2 units sold
    before, _ = paid_order(place, staff_client, items=[{"sku": PEPPER_2, "quantity": 1}])
    Order.objects.filter(number=before).update(created_at=now() - timedelta(days=4))
    OrderItem.objects.filter(order__number=before).update(promotion=None)
    paid_order(place, staff_client, items=[{"sku": PEPPER_2, "quantity": 2}])

    row = report(staff_client)["promotions"][0]
    assert row["id"] == promo.id and row["orders"] == 1 and row["units"] == 2
    assert row["units_per_day_before"] == pytest.approx(1 / 3, abs=0.01)
    assert row["units_per_day"] == pytest.approx(2 / 3, abs=0.01)
    assert row["lift_percent"] == 100
    assert row["discount_satang"] == 2 * (8500 - 7650)          # 2 units at 8.50 off each
    assert row["revenue_satang"] == 2 * 7650


def test_no_lift_is_reported_when_there_was_nothing_before(staff_client, place, seeded):
    promo = Promotion.objects.create(name="ใหม่", kind="percent", value=10, scope="all", starts_at=now() - timedelta(days=1))
    paid_order(place, staff_client, items=[{"sku": PEPPER_2, "quantity": 1}])
    row = next(r for r in report(staff_client)["promotions"] if r["id"] == promo.id)
    assert row["lift_percent"] is None


def test_unpaid_and_cancelled_orders_do_not_count(staff_client, place, seeded):
    promo = Promotion.objects.create(name="x", kind="percent", value=10, scope="all", starts_at=now() - timedelta(days=1))
    place(items=[{"sku": PEPPER_2, "quantity": 5}])                 # unpaid
    n, _ = paid_order(place, staff_client, items=[{"sku": PEPPER_2, "quantity": 1}])
    staff_client.post(f"/api/admin/orders/{n}/status", {"status": "cancelled"}, content_type="application/json")
    row = next(r for r in report(staff_client)["promotions"] if r["id"] == promo.id)
    assert row["orders"] == 0 and row["units"] == 0


def test_promotions_not_running_in_the_window_are_left_out(staff_client, seeded):
    Promotion.objects.create(name="เก่ามาก", kind="percent", value=10, scope="all",
                             starts_at=now() - timedelta(days=90), ends_at=now() - timedelta(days=80))
    assert report(staff_client, days=30)["promotions"] == []


def test_coupon_report_counts_uses_discount_and_cancellations(staff_client, place, client, seeded):
    Coupon.objects.create(code="WEEK10", name="x", kind="percent", value=10, per_phone_limit=None, starts_at=now() - timedelta(days=1))
    for phone in ("0811111111", "0822222222"):
        paid_order(place, staff_client, coupon_code="WEEK10", phone=phone, items=[{"sku": PEPPER_2, "quantity": 1}])   # 85 -> 76.50
    cancelled = place(coupon_code="WEEK10", phone="0833333333", items=[{"sku": PEPPER_2, "quantity": 1}]).json()["number"]
    staff_client.post(f"/api/admin/orders/{cancelled}/status", {"status": "cancelled"}, content_type="application/json")

    row = next(c for c in report(staff_client)["coupons"] if c["code"] == "WEEK10")
    assert (row["uses"], row["cancelled"], row["orders"]) == (2, 1, 2)
    assert row["discount_satang"] == 2 * 850 and row["average_discount_satang"] == 850
    assert row["revenue_satang"] == 2 * 7650


def test_free_shipping_orders_are_counted_in_the_coupon_row(staff_client, place, seeded):
    Coupon.objects.create(code="SHIPFREE", name="x", kind="free_shipping", value=1, per_phone_limit=None, starts_at=now() - timedelta(days=1))
    paid_order(place, staff_client, coupon_code="SHIPFREE", shipping_method="cargo-ubon", items=[{"sku": PEPPER_2, "quantity": 1}])
    row = next(c for c in report(staff_client)["coupons"] if c["code"] == "SHIPFREE")
    assert row["free_shipping_orders"] == 1 and row["discount_satang"] == 0


def test_only_reports_viewers_can_open_it(as_role):
    assert as_role("sales").get("/api/admin/reports/campaigns").status_code == 403
    assert as_role("manager").get("/api/admin/reports/campaigns").status_code == 200
