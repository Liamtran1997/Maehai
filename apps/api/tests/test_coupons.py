from datetime import timedelta

import pytest
from django.utils import timezone

from maehai.catalog.models import Product
from maehai.coupons.models import Coupon, CouponRedemption
from maehai.coupons.services import CouponError, Line, evaluate
from maehai.orders.models import Order

pytestmark = pytest.mark.django_db
JSON = "application/json"
PEPPER = "moo-yo-black-pepper-2"      # 85.00
NAEM = "naem-pork-1"                  # 60.00


def now():
    return timezone.now()


def coupon(staff, **over):
    body = {"code": "SAVE50", "name": "ลด 50 บาท", "kind": "amount", "value": 5000,
            "starts_at": (now() - timedelta(hours=1)).isoformat()}
    body.update(over)
    return staff.post("/api/admin/coupons", body, content_type=JSON)


def check(client, code, items=None, phone="", **kw):
    items = [{"sku": PEPPER, "quantity": 2}, {"sku": NAEM, "quantity": 1}] if items is None else items   # 230.00
    return client.post("/api/coupons/validate", {"code": code, "items": items, "phone": phone, **kw}, content_type=JSON, REMOTE_ADDR=kw.get("ip", "10.1.1.1"))


def order(place, code="", **over):
    return place(coupon_code=code, **over)


# ======================================================== evaluation (pure rules)
def L(total, promoted=False, sku="x"):
    return Line(sku=sku, quantity=1, unit_satang=total, promoted=promoted)


def make(**over):
    base = dict(code="C1", name="n", kind="amount", value=1000, starts_at=now() - timedelta(hours=1))
    return Coupon.objects.create(**{**base, **over})


@pytest.mark.parametrize("kw, total, expected", [
    ({"kind": "amount", "value": 5000}, 23000, 5000),
    ({"kind": "amount", "value": 99999}, 23000, 22900),                       # never below 1 baht left to pay
    ({"kind": "percent", "value": 10}, 23000, 2300),
    ({"kind": "percent", "value": 10}, 10050, 1005),
    ({"kind": "percent", "value": 10}, 10005, 1001),                          # 1000.5 rounds half up
    ({"kind": "percent", "value": 50, "max_discount_satang": 3000}, 23000, 3000),   # cap
])
def test_discount_math(kw, total, expected):
    make(**kw)
    assert evaluate("c1", [L(total)]).discount_satang == expected


def test_code_is_case_and_space_insensitive():
    make()
    assert evaluate("  c1 ", [L(5000)]).coupon.code == "C1"


@pytest.mark.parametrize("kw, msg", [
    ({"is_active": False}, "ไม่พบโค้ด"),
    ({"starts_at": now() + timedelta(days=1)}, "ไม่พบโค้ด"),
    ({"starts_at": now() - timedelta(days=2), "ends_at": now() - timedelta(hours=1)}, "ไม่พบโค้ด"),
])
def test_unusable_codes_all_look_the_same_to_a_guesser(kw, msg):
    make(**kw)
    with pytest.raises(CouponError, match=msg):
        evaluate("C1", [L(5000)])


def test_unknown_and_malformed_codes():
    for bad in ("NOPE", "", "!!", "x" * 40):
        with pytest.raises(CouponError, match="ไม่พบโค้ด"):
            evaluate(bad, [L(5000)])


def test_minimum_spend_explains_how_much_is_missing():
    make(min_subtotal_satang=50000)
    with pytest.raises(CouponError) as e:
        evaluate("C1", [L(23000)])
    assert "฿500.00" in str(e.value.message) and "฿270.00" in str(e.value.message)


def test_excluding_discounted_items():
    make(exclude_discounted_items=True, kind="percent", value=10, min_subtotal_satang=10000)
    ev = evaluate("C1", [L(10000), L(20000, promoted=True)])      # only the 100.00 counts
    assert ev.discount_satang == 1000 and ev.subtotal_satang == 30000
    with pytest.raises(CouponError, match="ลดราคาอยู่แล้ว"):
        evaluate("C1", [L(20000, promoted=True)])
    with pytest.raises(CouponError, match="ซื้อครบ"):
        evaluate("C1", [L(5000), L(90000, promoted=True)])        # promoted items do not help reach the minimum


# ======================================================== staff management
def test_staff_only(client, seeded):
    assert client.get("/api/admin/coupons").status_code == 401
    assert client.post("/api/admin/coupons", {}, content_type=JSON).status_code == 401


def test_create_normalises_code_and_rejects_bad_input(staff_client, seeded):
    assert coupon(staff_client, code=" save50 ").json()["code"] == "SAVE50"
    assert coupon(staff_client).status_code == 409                                         # duplicate
    for over in ({"code": "a"}, {"code": "BAD CODE"}, {"kind": "x"}, {"kind": "percent", "value": 95},
                 {"value": 0}, {"ends_at": "2020-01-01T00:00:00+07:00"}, {"max_discount_satang": 100},
                 {"usage_limit": 0}):
        assert coupon(staff_client, **{"code": "OTHER", **over}).status_code == 422, over


def test_state_and_usage_numbers(client, staff_client, place):
    c = coupon(staff_client, usage_limit=2, per_phone_limit=None).json()
    assert c["state"] == "running" and c["remaining"] == 2
    order(place, "SAVE50")
    listed = staff_client.get("/api/admin/coupons").json()[0]
    assert (listed["used_count"], listed["remaining"], listed["discount_given_satang"]) == (1, 1, 5000)
    order(place, "SAVE50", phone="0899999999")
    assert staff_client.get("/api/admin/coupons").json()[0]["state"] == "exhausted"


def test_end_delete_and_code_change_rules(client, staff_client, place):
    c = coupon(staff_client).json()
    order(place, "SAVE50")
    assert staff_client.delete(f"/api/admin/coupons/{c['id']}").status_code == 409         # used: keep history
    body = {**{k: c[k] for k in ("name", "kind", "value", "starts_at")}, "code": "RENAMED"}
    assert staff_client.put(f"/api/admin/coupons/{c['id']}", body, content_type=JSON).status_code == 409
    ended = staff_client.post(f"/api/admin/coupons/{c['id']}/end").json()
    assert ended["state"] == "ended"
    assert check(client, "SAVE50").status_code == 422
    unused = coupon(staff_client, code="NEVERUSED").json()
    assert staff_client.delete(f"/api/admin/coupons/{unused['id']}").status_code == 204


def test_redemption_history(staff_client, place):
    c = coupon(staff_client).json()
    n = order(place, "SAVE50").json()["number"]
    rows = staff_client.get(f"/api/admin/coupons/{c['id']}/redemptions").json()
    assert rows[0]["order_number"] == n and rows[0]["discount_satang"] == 5000 and rows[0]["released"] is False


# ======================================================== checkout preview
def test_preview_shows_the_discount(client, staff_client, seeded):
    coupon(staff_client)
    r = check(client, "save50").json()
    assert (r["subtotal_satang"], r["discount_satang"], r["goods_total_satang"], r["label"]) == (23000, 5000, 18000, "ลด ฿50")


def test_preview_tells_why_it_fails(client, staff_client, seeded):
    coupon(staff_client, min_subtotal_satang=100000)
    r = check(client, "SAVE50")
    assert r.status_code == 422 and "ซื้อครบ" in r.json()["detail"]
    assert check(client, "NOPE").json()["detail"].startswith("ไม่พบโค้ด")


def test_preview_uses_sale_prices_and_can_skip_promoted_items(client, staff_client, seeded):
    pid = Product.objects.get(slug="moo-yo-black-pepper").id
    staff_client.post("/api/admin/catalog/promotions", {"name": "ลด", "kind": "percent", "value": 10, "scope": "products",
        "product_ids": [pid], "starts_at": (now() - timedelta(hours=1)).isoformat()}, content_type=JSON)
    coupon(staff_client, kind="percent", value=10, code="TEN", exclude_discounted_items=True)
    r = check(client, "TEN", items=[{"sku": PEPPER, "quantity": 2}, {"sku": NAEM, "quantity": 1}]).json()
    assert r["subtotal_satang"] == 7650 * 2 + 6000          # sale price already applied
    assert r["discount_satang"] == 600                      # 10% of the 60.00 naem only


def test_preview_checks_phone_limit_when_phone_is_given(client, staff_client, place):
    coupon(staff_client)
    order(place, "SAVE50")                                            # phone 0812345678 used its one use
    assert check(client, "SAVE50", phone="081-234-5678").status_code == 422
    assert check(client, "SAVE50", phone="0899999999").status_code == 200
    assert check(client, "SAVE50", phone="12").status_code == 200     # half-typed phone does not block the preview


def test_preview_validates_the_cart(client, staff_client, seeded):
    coupon(staff_client)
    assert check(client, "SAVE50", items=[]).status_code == 422
    assert check(client, "SAVE50", items=[{"sku": "nope", "quantity": 1}]).status_code == 422
    assert check(client, "SAVE50", items=[{"sku": NAEM, "quantity": 0}]).status_code == 422


# ======================================================== placing an order with a coupon
def test_order_gets_the_discount_and_remembers_it(client, staff_client, place):
    coupon(staff_client)
    o = order(place, "save50").json()                       # 85*1 + 60*2 = 205.00
    assert (o["subtotal_satang"], o["coupon_code"], o["coupon_discount_satang"], o["total_satang"]) == (20500, "SAVE50", 5000, 15500)
    assert client.get(f"/api/orders/{o['number']}", {"token": o["token"]}).json()["total_satang"] == 15500
    assert CouponRedemption.objects.get(order__number=o["number"]).discount_satang == 5000


def test_the_qr_charges_the_discounted_amount(client, staff_client, place):
    coupon(staff_client)
    o = order(place, "SAVE50").json()
    p = client.post(f"/api/payments/{o['number']}/charge?token={o['token']}").json()
    assert p["amount_satang"] == 15500 and "155.00" in p["qr_payload"]


def test_coupon_with_delivery_applies_to_goods_not_shipping(client, staff_client, place):
    coupon(staff_client)
    o = order(place, "SAVE50", shipping_method="cargo-ubon").json()
    assert o["total_satang"] is None                                         # shipping not quoted yet
    r = staff_client.post(f"/api/admin/orders/{o['number']}/fee", {"fee_satang": 12000}, content_type=JSON).json()
    assert r["total_satang"] == 20500 - 5000 + 12000 and r["coupon_discount_satang"] == 5000


def test_vat_is_taken_from_the_amount_after_the_coupon(client, staff_client, place, settings):
    settings.VAT_ENABLED = True
    coupon(staff_client)
    o = order(place, "SAVE50").json()
    assert o["vat_satang"] == round(15500 * 7 / 107)


def test_bad_coupon_rejects_the_order_and_creates_nothing(place, staff_client):
    r = order(place, "NOPE")
    assert r.status_code == 422 and Order.objects.count() == 0 and CouponRedemption.objects.count() == 0


def test_stock_is_not_reserved_when_the_coupon_fails(place, staff_client):
    from maehai.catalog.models import ProductVariant
    from maehai.inventory.models import StockLevel

    ProductVariant.objects.filter(sku=NAEM).update(track_stock=True)
    staff_client.post("/api/admin/inventory/adjust", {"branch": "srinarong", "sku": NAEM, "reason": "receive", "quantity": 9}, content_type=JSON)
    order(place, "NOPE")
    assert StockLevel.objects.get(variant__sku=NAEM, branch__code="srinarong").reserved == 0


# ======================================================== limits
def test_one_use_per_phone_by_default(staff_client, place):
    coupon(staff_client)
    assert order(place, "SAVE50").status_code == 201
    again = order(place, "SAVE50")
    assert again.status_code == 422 and "ครบสิทธิ์" in again.json()["detail"]
    assert order(place, "SAVE50", phone="0899999999").status_code == 201
    assert order(place, "").status_code == 201                        # the same phone can still order without it


def test_phone_format_does_not_dodge_the_limit(staff_client, place):
    coupon(staff_client)
    order(place, "SAVE50", phone="081-234-5678")
    assert order(place, "SAVE50", phone="+66 81 234 5678").status_code == 422


def test_total_usage_limit(staff_client, place):
    coupon(staff_client, usage_limit=2, per_phone_limit=None)
    assert [order(place, "SAVE50", phone=f"08{i}0000000").status_code for i in (1, 2, 3)] == [201, 201, 422]


def test_cancelling_gives_the_use_back(staff_client, place):
    coupon(staff_client, usage_limit=1)
    n = order(place, "SAVE50").json()["number"]
    assert order(place, "SAVE50", phone="0899999999").status_code == 422          # used up
    staff_client.post(f"/api/admin/orders/{n}/status", {"status": "cancelled"}, content_type=JSON)
    assert CouponRedemption.objects.get(order__number=n).released_at is not None
    assert order(place, "SAVE50", phone="0899999999").status_code == 201          # available again
    assert staff_client.get("/api/admin/coupons").json()[0]["used_count"] == 1


def test_unpaid_expiry_also_gives_the_use_back(staff_client, place):
    from django.core.management import call_command
    from io import StringIO

    coupon(staff_client, usage_limit=1)
    n = order(place, "SAVE50").json()["number"]
    Order.objects.filter(number=n).update(created_at=now() - timedelta(hours=30))
    call_command("expire_unpaid_orders", stdout=StringIO())
    assert order(place, "SAVE50", phone="0899999999").status_code == 201


def test_discount_never_makes_the_goods_free(staff_client, place):
    coupon(staff_client, value=1_000_000)                                           # 10,000 baht off
    o = order(place, "SAVE50", items=[{"sku": NAEM, "quantity": 1}]).json()         # 60.00
    assert o["coupon_discount_satang"] == 5900 and o["total_satang"] == 100


# ======================================================== guessing is throttled
def test_code_guessing_is_blocked_after_repeated_failures(client, settings, staff_client, seeded):
    settings.RATE_LIMIT_ENABLED = True
    settings.RATE_LIMITS = {**settings.RATE_LIMITS, "coupon_fail_ip": (3, 900)}
    coupon(staff_client)
    for i in range(3):
        assert check(client, f"GUESS{i}", ip="10.7.7.7").status_code == 422
    r = check(client, "SAVE50", ip="10.7.7.7")                                      # even the right code is refused now
    assert r.status_code == 429 and r["Retry-After"]
    assert check(client, "SAVE50", ip="10.7.7.8").status_code == 200                # other visitors unaffected


def test_guessing_through_checkout_counts_too(client, place, settings, staff_client):
    settings.RATE_LIMIT_ENABLED = True
    settings.RATE_LIMITS = {**settings.RATE_LIMITS, "coupon_fail_ip": (2, 900), "order_create_ip": (50, 3600), "order_create_phone": (50, 3600)}
    for i in range(2):
        assert order(place, f"GUESS{i}").status_code == 422
    assert order(place, "GUESS9").status_code == 429


@pytest.mark.django_db(transaction=True)
def test_concurrent_orders_cannot_both_take_the_last_use(seeded, staff_client, order_payload):
    """Eight customers press "order" at the same instant for a coupon with one use left. Exactly one may win.
    Needs real row locks, so it runs on Postgres (SQLite serialises writers by itself and cannot reproduce the race)."""
    import threading

    from django.db import connection, connections
    from django.test import Client

    if connection.vendor != "postgresql":
        pytest.skip("row locks need Postgres")
    coupon(staff_client, usage_limit=1, per_phone_limit=None)
    results, barrier = [], threading.Barrier(8)

    def go(i):
        try:
            barrier.wait()
            r = Client().post("/api/orders", {**order_payload(phone=f"081000000{i}"), "coupon_code": "SAVE50"}, content_type=JSON)
            results.append(r.status_code)
        finally:
            connections.close_all()

    threads = [threading.Thread(target=go, args=(i,)) for i in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert sorted(results) == [201] + [422] * 7, results
    assert CouponRedemption.objects.filter(released_at__isnull=True).count() == 1
