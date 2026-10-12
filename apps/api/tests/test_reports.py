from datetime import timedelta

import pytest
from django.utils import timezone

from maehai.orders.models import Order
from maehai.payments.models import Payment

pytestmark = pytest.mark.django_db


def paid_order(place, staff_client, **over):
    """Place an order and confirm payment the way staff would. Returns the order number."""
    from django.test import Client

    o = place(**over).json()
    c = Client()
    tok = f"token={o['token']}"
    if o["status"] == "pending_quote":
        staff_client.post(f"/api/admin/orders/{o['number']}/fee", {"fee_satang": 12000}, content_type="application/json")
    pid = c.post(f"/api/payments/{o['number']}/charge?{tok}").json()["id"]
    staff_client.post(f"/api/admin/payments/{pid}/confirm")
    return o["number"], pid


def test_requires_staff(client, seeded):
    assert client.get("/api/admin/reports/summary").status_code == 401


def test_empty_shop_returns_zeroes(staff_client, seeded):
    r = staff_client.get("/api/admin/reports/summary", {"days": 7}).json()
    assert r["current"] == {"revenue_satang": 0, "paid_orders": 0, "avg_order_satang": 0}
    assert len(r["daily"]) == 7 and all(d["revenue_satang"] == 0 for d in r["daily"])
    assert r["top_products"] == [] and r["by_shipping"] == []


def test_revenue_counts_only_confirmed_payments(staff_client, place, client):
    paid_order(place, staff_client)                      # 205.00, pickup
    paid_order(place, staff_client, shipping_method="cargo-ubon")   # 205.00 + 120.00 ship
    place()                                              # unpaid: must not count
    r = staff_client.get("/api/admin/reports/summary", {"days": 7}).json()
    assert r["current"]["revenue_satang"] == 20500 + 32500
    assert r["current"]["paid_orders"] == 2
    assert r["current"]["avg_order_satang"] == (20500 + 32500) // 2
    assert r["orders_created"] == 3
    assert r["daily"][-1]["revenue_satang"] == 53000          # today is the last bar
    assert r["todo"]["waiting_payment"] == 1 and r["todo"]["to_pack"] == 2


def test_top_products_and_shipping_breakdown(staff_client, place):
    paid_order(place, staff_client)
    paid_order(place, staff_client, shipping_method="cargo-ubon")
    r = staff_client.get("/api/admin/reports/summary").json()
    top = {t["name"]: t["quantity"] for t in r["top_products"]}
    assert top == {"แหนมหมู": 4, "หมูยอพริกไทยดำ": 2}
    ship = {s["name"]: s["revenue_satang"] for s in r["by_shipping"]}
    assert ship == {"รับที่ร้าน สาขาศรีณรงค์": 20500, "สหฯอุบลคาร์โก้": 32500}


def test_previous_period_and_window_edges(staff_client, place):
    _, pid = paid_order(place, staff_client)
    # a sale confirmed 10 days ago falls in the previous 7-day period, not the current one
    Payment.objects.filter(pk=pid).update(confirmed_at=timezone.now() - timedelta(days=10))
    r = staff_client.get("/api/admin/reports/summary", {"days": 7}).json()
    assert r["current"]["revenue_satang"] == 0 and r["previous"]["revenue_satang"] == 20500
    assert staff_client.get("/api/admin/reports/summary", {"days": 30}).json()["current"]["revenue_satang"] == 20500


def test_todo_slips(staff_client, place, client):
    o = place().json()
    client.post(f"/api/payments/{o['number']}/charge?token={o['token']}")
    from io import BytesIO
    from django.core.files.uploadedfile import SimpleUploadedFile
    from PIL import Image

    buf = BytesIO(); Image.new("RGB", (2, 2)).save(buf, "PNG")
    client.post(f"/api/payments/{o['number']}/slip?token={o['token']}", {"slip": SimpleUploadedFile("s.png", buf.getvalue(), content_type="image/png")})
    assert staff_client.get("/api/admin/reports/summary").json()["todo"]["slips_to_check"] == 1


@pytest.mark.parametrize("days", [0, 91])
def test_days_validated(staff_client, seeded, days):
    assert staff_client.get("/api/admin/reports/summary", {"days": days}).status_code == 422
