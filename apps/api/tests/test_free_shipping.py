import pytest
from datetime import timedelta

from django.utils import timezone

from maehai.coupons.models import Coupon, CouponRedemption
from maehai.coupons.services import CouponError, Line, evaluate
from maehai.orders.models import Order

pytestmark = pytest.mark.django_db
JSON = "application/json"
NAEM = "naem-pork-1"


def ship_coupon(staff, code="FREESHIP", **over):
    body = {"code": code, "name": "ส่งฟรี", "kind": "free_shipping", "value": 1,
            "starts_at": (timezone.now() - timedelta(hours=1)).isoformat(), **over}
    return staff.post("/api/admin/coupons", body, content_type=JSON)


def preview(client, code, method):
    return client.post("/api/coupons/validate", {"code": code, "items": [{"sku": NAEM, "quantity": 1}],
                                                  "shipping_method": method}, content_type=JSON, REMOTE_ADDR="10.8.8.8")


def test_free_shipping_is_its_own_kind_and_says_so(staff_client, seeded):
    r = ship_coupon(staff_client)
    assert r.status_code == 201 and r.json()["kind"] == "free_shipping" and r.json()["label"] == "ส่งฟรี"


def test_free_shipping_cannot_have_a_cap(staff_client, seeded):
    assert ship_coupon(staff_client, max_discount_satang=3000).status_code == 422


def test_preview_waives_shipping_for_delivery_but_not_pickup(client, staff_client, seeded):
    ship_coupon(staff_client)
    ok = preview(client, "freeship", "cargo-ubon").json()
    assert ok["shipping_waived"] is True and ok["discount_satang"] == 0 and ok["goods_total_satang"] == 6000
    no = preview(client, "FREESHIP", "pickup-srinarong")
    assert no.status_code == 422 and "จัดส่ง" in no.json()["detail"]


def test_delivery_order_goes_straight_to_payment_with_no_fee(client, staff_client, place):
    ship_coupon(staff_client)
    o = place(shipping_method="cargo-ubon", coupon_code="FREESHIP").json()
    assert o["status"] == "waiting_payment" and o["shipping_waived"] is True
    assert o["shipping_fee_satang"] == 0 and o["total_satang"] == 20500 and o["coupon_discount_satang"] == 0   # default cart: 205.00
    assert CouponRedemption.objects.filter(order__number=o["number"]).exists()    # the use is still counted


def test_staff_cannot_quote_a_fee_on_a_free_shipping_order(staff_client, place, client):
    ship_coupon(staff_client)
    n = place(shipping_method="cargo-ubon", coupon_code="FREESHIP").json()["number"]
    r = staff_client.post(f"/api/admin/orders/{n}/fee", {"fee_satang": 12000}, content_type=JSON)
    assert r.status_code == 409 and "ส่งฟรี" in r.json()["detail"]


def test_pickup_order_cannot_use_it(staff_client, place):
    ship_coupon(staff_client)
    r = place(shipping_method="pickup-srinarong", coupon_code="FREESHIP")
    assert r.status_code == 422 and Order.objects.count() == 0


def test_free_shipping_still_obeys_minimum_spend(staff_client, place):
    ship_coupon(staff_client, min_subtotal_satang=100000)
    assert place(shipping_method="cargo-ubon", coupon_code="FREESHIP").status_code == 422


def test_cancelling_gives_the_free_shipping_use_back(staff_client, place):
    ship_coupon(staff_client, usage_limit=1, per_phone_limit=None)
    n = place(shipping_method="cargo-ubon", coupon_code="FREESHIP").json()["number"]
    assert place(shipping_method="cargo-ubon", coupon_code="FREESHIP", phone="0899999999").status_code == 422
    staff_client.post(f"/api/admin/orders/{n}/status", {"status": "cancelled"}, content_type=JSON)
    assert place(shipping_method="cargo-ubon", coupon_code="FREESHIP", phone="0899999999").status_code == 201


def test_evaluate_direct_rule(db):
    Coupon.objects.create(code="SHIPFREE", name="x", kind="free_shipping", value=1, starts_at=timezone.now() - timedelta(hours=1))
    ev = evaluate("shipfree", [Line(sku="a", quantity=1, unit_satang=5000, promoted=False)], shipping_applies=True)
    assert ev.shipping_waived and ev.discount_satang == 0
    with pytest.raises(CouponError):
        evaluate("SHIPFREE", [Line(sku="a", quantity=1, unit_satang=5000, promoted=False)], shipping_applies=False)
