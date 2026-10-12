import json

import pytest

from maehai.orders.models import Order
from maehai.shipping.schedule import earliest_fulfillment_date

pytestmark = pytest.mark.django_db
JSON = "application/json"


def test_pickup_order_is_priced_on_the_server(place):
    r = place()
    assert r.status_code == 201, r.content
    o = r.json()
    # black pepper (กลาง) 85.00 x1 + naem 60.00 x2
    assert o["subtotal_satang"] == 8500 + 12000
    assert o["shipping_fee_satang"] == 0 and o["total_satang"] == 20500
    assert o["status"] == "waiting_payment"
    assert o["phone"] == "0812345678"
    assert o["number"].startswith("MH-2569-") or o["number"].startswith("MH-25")  # Buddhist-era year
    assert {i["sku"] for i in o["items"]} == {"moo-yo-black-pepper-2", "naem-pork-1"}


def test_item_snapshot_survives_price_change(place):
    from maehai.catalog.models import ProductVariant

    number = place().json()["number"]
    ProductVariant.objects.filter(sku="naem-pork-1").update(price_satang=99900)
    item = Order.objects.get(number=number).items.get(sku="naem-pork-1")
    assert item.unit_price_satang == 6000


def test_duplicate_skus_are_merged(place):
    r = place(items=[{"sku": "naem-pork-1", "quantity": 1}, {"sku": "naem-pork-1", "quantity": 2}])
    assert [i["quantity"] for i in r.json()["items"]] == [3]


def test_carrier_order_waits_for_fee_quote(place):
    o = place(shipping_method="cargo-ubon").json()
    assert o["status"] == "pending_quote" and o["shipping_fee_satang"] is None and o["total_satang"] is None


@pytest.mark.parametrize("over, msg", [
    ({"items": []}, "ตะกร้า"),
    ({"items": [{"sku": "naem-pork-1", "quantity": 0}]}, "จำนวน"),
    ({"items": [{"sku": "naem-pork-1", "quantity": 100}]}, "จำนวน"),
    ({"items": [{"sku": "no-such-sku", "quantity": 1}]}, "no-such-sku"),
    ({"phone": "12345"}, "เบอร์"),
    ({"shipping_method": "teleport"}, "วิธีรับ"),
    ({"shipping_method": "parcel"}, "ที่อยู่"),
    ({"shipping_method": "parcel", "address": {"address_line": "1", "province": "กรุงเทพฯ", "postal_code": "1234"}}, "5 หลัก"),
    ({"requested_date": "2020-01-01"}, "13:00"),
])
def test_validation(place, over, msg):
    r = place(**over)
    assert r.status_code == 422, r.content
    assert msg in r.content.decode("unicode_escape") or msg in json.dumps(r.json(), ensure_ascii=False)


def test_inactive_product_cannot_be_ordered(place):
    from maehai.catalog.models import Product

    Product.objects.filter(slug="naem-pork").update(is_active=False)
    assert place().status_code == 422


def test_sunday_rejected(place):
    from datetime import date, timedelta

    d = earliest_fulfillment_date()
    while d.weekday() != 6:
        d += timedelta(days=1)
    assert place(requested_date=d.isoformat()).status_code == 422


def test_parcel_with_address_ok(place):
    o = place(shipping_method="parcel", address={"address_line": "99/1 ถ.ชยางกูร", "province": "อุบลราชธานี", "postal_code": "34000"}).json()
    assert o["status"] == "pending_quote" and o["postal_code"] == "34000"


def test_token_and_lookup(client, place):
    o = place().json()
    assert client.get(f"/api/orders/{o['number']}", {"token": o["token"]}).status_code == 200
    assert client.get(f"/api/orders/{o['number']}", {"token": "wrong"}).status_code == 404
    ok = client.post("/api/orders/lookup", {"number": o["number"], "phone": "0812345678"}, content_type=JSON)
    assert ok.json()["token"] == o["token"]
    assert client.post("/api/orders/lookup", {"number": o["number"], "phone": "0899999999"}, content_type=JSON).status_code == 404


def test_fee_quote_flow(client, staff_client, place):
    o = place(shipping_method="cargo-ubon").json()
    assert client.post(f"/api/admin/orders/{o['number']}/fee", {"fee_satang": 12000}, content_type=JSON).status_code == 401
    r = staff_client.post(f"/api/admin/orders/{o['number']}/fee", {"fee_satang": 12000}, content_type=JSON)
    assert r.status_code == 200
    j = r.json()
    assert j["status"] == "waiting_payment" and j["total_satang"] == 20500 + 12000
    assert any(e["kind"] == "fee_quoted" for e in j["events"])


def test_status_transitions(staff_client, place):
    num = place().json()["number"]  # waiting_payment
    set_status = lambda s, **kw: staff_client.post(f"/api/admin/orders/{num}/status", {"status": s, **kw}, content_type=JSON)
    assert set_status("paid").status_code == 409        # money states only via payment confirmation
    assert set_status("packing").status_code == 409     # cannot skip payment
    assert set_status("cancelled").status_code == 200
    assert set_status("packing").status_code == 409     # cancelled is final


def test_admin_list_filters_and_paginates(staff_client, place):
    place(); place(shipping_method="cargo-ubon")
    r = staff_client.get("/api/admin/orders", {"status": "pending_quote"})
    assert r.status_code == 200 and r.json()["count"] == 1
    assert staff_client.get("/api/admin/orders", {"q": "081-234"}).json()["count"] == 2


def test_order_needs_the_privacy_consent(place):
    r = place(accepted_terms=False)
    assert r.status_code == 422 and "ยอมรับ" in r.json()["detail"]
    assert Order.objects.count() == 0


def test_consent_time_is_recorded(place):
    o = place().json()
    assert Order.objects.get(number=o["number"]).terms_accepted_at is not None
