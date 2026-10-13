from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.utils import timezone

from maehai.catalog.models import ProductVariant
from maehai.inventory.models import Branch, StockLevel, StockMovement, StockReservation
from maehai.notifications.models import Outbox
from maehai.orders.models import Order
from tests.warehouse import send_and_confirm, stock_in

pytestmark = pytest.mark.django_db
JSON = "application/json"
PEPPER, NAEM = "moo-yo-black-pepper-2", "naem-pork-1"


def api_post(c, url, data, content_type=JSON):
    return c.post(url, data, content_type=content_type)


@pytest.fixture
def stocked(seeded, staff_client):
    """Track both items; Srinarong has 5 pepper + 5 naem, Changsanit has 5 naem and no pepper."""
    ProductVariant.objects.filter(sku__in=[PEPPER, NAEM]).update(track_stock=True)
    stock_in(staff_client, "srinarong", PEPPER, 5)
    stock_in(staff_client, "srinarong", NAEM, 5)
    stock_in(staff_client, "changsanit", NAEM, 5)
    return staff_client


def level(branch, sku):
    return StockLevel.objects.get(branch__code=branch, variant__sku=sku)


def order_for(place, items, method="pickup-srinarong"):
    return place(items=[{"sku": s, "quantity": q} for s, q in items], shipping_method=method)


# ---------- reserving ----------
def test_untracked_items_are_sold_without_counting(place):
    assert order_for(place, [(PEPPER, 50)]).status_code == 201
    assert StockReservation.objects.count() == 0


def test_tracked_item_with_no_stock_cannot_be_ordered(place):
    ProductVariant.objects.filter(sku=PEPPER).update(track_stock=True)
    r = order_for(place, [(PEPPER, 1)])
    assert r.status_code == 409 and "เหลือ 0" in r.json()["detail"] and Order.objects.count() == 0


def test_order_reserves_and_lowers_availability(place, stocked):
    r = order_for(place, [(PEPPER, 2), (NAEM, 1)])
    assert r.status_code == 201 and r.json()["fulfillment_branch"]["code"] == "srinarong"
    assert (level("srinarong", PEPPER).on_hand, level("srinarong", PEPPER).reserved) == (5, 2)
    assert level("srinarong", NAEM).available == 4


def test_the_last_unit_goes_to_one_customer_only(place, stocked):
    assert order_for(place, [(PEPPER, 5)]).status_code == 201
    r = order_for(place, [(PEPPER, 1)])
    assert r.status_code == 409 and "เหลือ 0" in r.json()["detail"]
    assert level("srinarong", PEPPER).reserved == 5


def test_partial_shortage_rolls_everything_back(place, stocked):
    r = order_for(place, [(NAEM, 3), (PEPPER, 6)])         # naem fits, pepper does not
    assert r.status_code == 409
    assert level("srinarong", NAEM).reserved == 0 and Order.objects.count() == 0 and StockReservation.objects.count() == 0


def test_pickup_uses_the_customers_branch(place, stocked):
    r = order_for(place, [(NAEM, 2)], method="pickup-changsanit")
    assert r.json()["fulfillment_branch"]["code"] == "changsanit" and level("changsanit", NAEM).reserved == 2
    assert order_for(place, [(PEPPER, 1)], method="pickup-changsanit").status_code == 409   # that branch has none


def test_delivery_prefers_default_branch_then_falls_back(place, stocked):
    assert order_for(place, [(NAEM, 4)], method="cargo-ubon").json()["fulfillment_branch"]["code"] == "srinarong"
    r = order_for(place, [(NAEM, 3)], method="cargo-ubon")  # srinarong has 1 left, changsanit has 5
    assert r.json()["fulfillment_branch"]["code"] == "changsanit"


def test_delivery_never_splits_an_order_across_branches(place, stocked):
    order_for(place, [(NAEM, 4)], method="cargo-ubon")      # srinarong: 1 naem left
    r = order_for(place, [(NAEM, 2), (PEPPER, 2)], method="cargo-ubon")   # pepper only at srinarong, naem now only whole at changsanit
    assert r.status_code == 409


# ---------- lifecycle ----------
def paid_packing(client, staff, number):
    from tests.test_payments import charge

    o = Order.objects.get(number=number)
    pid = charge(client, {"number": number, "token": o.public_token}).json()["id"]
    staff.post(f"/api/admin/payments/{pid}/confirm")
    assert api_post(staff, f"/api/admin/orders/{number}/status", {"status": "packing"}).status_code == 200


def set_status(staff, number, status, **kw):
    return api_post(staff, f"/api/admin/orders/{number}/status", {"status": status, **kw})


def test_cancel_returns_stock(client, place, stocked):
    n = order_for(place, [(PEPPER, 3)]).json()["number"]
    assert set_status(stocked, n, "cancelled").status_code == 200
    assert level("srinarong", PEPPER).reserved == 0 and level("srinarong", PEPPER).on_hand == 5
    assert StockReservation.objects.get().state == "released"


def test_shipping_takes_stock_out_once(client, place, stocked):
    n = order_for(place, [(PEPPER, 2)], method="cargo-ubon").json()["number"]
    api_post(stocked, f"/api/admin/orders/{n}/fee", {"fee_satang": 12000})
    paid_packing(client, stocked, n)
    set_status(stocked, n, "shipped", tracking_ref="UB1")
    lv = level("srinarong", PEPPER)
    assert (lv.on_hand, lv.reserved) == (3, 0)
    set_status(stocked, n, "done")
    assert level("srinarong", PEPPER).on_hand == 3                 # not taken a second time
    m = StockMovement.objects.get(reason="sale")
    assert (m.delta, m.on_hand_after, m.order.number) == (-2, 3, n)


def test_counter_handover_takes_stock_out_when_done(client, place, stocked):
    n = order_for(place, [(NAEM, 2)]).json()["number"]
    paid_packing(client, stocked, n)
    set_status(stocked, n, "done")
    assert level("srinarong", NAEM).on_hand == 3


def test_cancel_during_packing_releases(client, place, stocked):
    n = order_for(place, [(NAEM, 2)]).json()["number"]
    paid_packing(client, stocked, n)
    set_status(stocked, n, "cancelled")
    lv = level("srinarong", NAEM)
    assert (lv.on_hand, lv.reserved) == (5, 0)


# ---------- staff stock changes ----------
def adjust(c, **kw):
    return api_post(c, "/api/admin/inventory/adjust", {"branch": "srinarong", "sku": PEPPER, **kw})


def test_waste_count_and_ledger(stocked):
    stock_in(stocked, "srinarong", PEPPER, 10)                       # 5 + 10 through a receipt
    assert adjust(stocked, reason="waste", quantity=2, note="หมดอายุ").json()["on_hand"] == 13
    assert adjust(stocked, reason="count", quantity=12).json()["on_hand"] == 12
    deltas = [m["delta"] for m in stocked.get("/api/admin/inventory/movements", {"sku": PEPPER}).json()]
    assert deltas == [-1, -2, 10, 5]                                # newest first
    assert stocked.get("/api/admin/inventory/movements").json()[0]["actor"] == "owner"


def test_cannot_drop_below_whats_promised(place, stocked):
    order_for(place, [(PEPPER, 4)])
    assert adjust(stocked, reason="waste", quantity=3).status_code == 409    # 5 - 3 = 2 < 4 reserved
    assert adjust(stocked, reason="count", quantity=3).status_code == 409
    assert adjust(stocked, reason="count", quantity=4).status_code == 200


@pytest.mark.parametrize("kw", [{"reason": "receive", "quantity": 1}, {"reason": "waste", "quantity": 99}, {"reason": "sale", "quantity": 1}])
def test_bad_adjustments(stocked, kw):
    assert adjust(stocked, **kw).status_code in (409, 422)


def on_hand(branch, sku):
    lv = StockLevel.objects.filter(branch__code=branch, variant__sku=sku).first()
    return lv.on_hand if lv else 0


def test_transfer_moves_stock_only_when_the_branch_confirms(stocked):
    doc = api_post(stocked, "/api/admin/inventory/documents/transfers",
                   {"to_branch": "changsanit", "vehicle": "กระบะ", "lines": [{"sku": PEPPER, "quantity": 2}]}, content_type=JSON).json()
    assert (on_hand("srinarong", PEPPER), on_hand("changsanit", PEPPER)) == (3, 0)               # in transit
    assert doc["status"] == "sent" and doc["number"].startswith("TR-")
    r = api_post(stocked, f"/api/admin/inventory/documents/{doc['number']}/receive",
                 {"lines": [{"line_id": doc["lines"][0]["id"], "received": 2}], "substitute_reason": "ทดสอบ"})
    assert r.status_code == 200, r.content
    assert (on_hand("srinarong", PEPPER), on_hand("changsanit", PEPPER)) == (3, 2)
    reasons = set(StockMovement.objects.filter(variant__sku=PEPPER).values_list("reason", flat=True))
    assert {"transfer_in", "transfer_out"} <= reasons


def test_transfer_cannot_take_reserved_stock(place, stocked):
    order_for(place, [(PEPPER, 4)])                                  # 5 on hand, 4 promised: only 1 can leave
    r = api_post(stocked, "/api/admin/inventory/documents/transfers",
                 {"to_branch": "changsanit", "vehicle": "กระบะ", "lines": [{"sku": PEPPER, "quantity": 2}]}, content_type=JSON)
    assert r.status_code == 409 and "มีให้ส่งได้แค่ 1" in r.json()["detail"]
    assert level("srinarong", PEPPER).on_hand == 5                   # nothing moved


def test_inventory_requires_staff(client, seeded):
    assert client.get("/api/admin/inventory/stock").status_code == 401
    assert client.post("/api/admin/inventory/adjust", {}, content_type=JSON).status_code == 401


def test_stock_table_lists_all_branches(stocked):
    row = next(r for r in stocked.get("/api/admin/inventory/stock").json() if r["sku"] == PEPPER)
    assert row["track_stock"] and {l["branch"]: l["on_hand"] for l in row["levels"] if l["branch"] in ("srinarong", "changsanit")} == {"srinarong": 5, "changsanit": 0}


def test_toggle_tracking(seeded, staff_client):
    r = api_post(staff_client, f"/api/admin/inventory/variants/{PEPPER}/track", {"track": True})
    assert r.status_code == 200 and r.json()["track_stock"] is True


def test_database_refuses_overbooking(stocked):
    with pytest.raises(IntegrityError), transaction.atomic():
        StockLevel.objects.filter(branch__code="srinarong", variant__sku=PEPPER).update(reserved=99)


# ---------- reassigning a delivery order ----------
def test_reassign_moves_the_reservation(place, stocked):
    n = order_for(place, [(NAEM, 2)], method="cargo-ubon").json()["number"]
    r = api_post(stocked, f"/api/admin/orders/{n}/branch", {"branch": "changsanit"})
    assert r.status_code == 200 and r.json()["fulfillment_branch"]["code"] == "changsanit"
    assert level("srinarong", NAEM).reserved == 0 and level("changsanit", NAEM).reserved == 2


def test_reassign_keeps_old_reservation_when_new_branch_is_short(place, stocked):
    n = order_for(place, [(PEPPER, 2)], method="cargo-ubon").json()["number"]
    r = api_post(stocked, f"/api/admin/orders/{n}/branch", {"branch": "changsanit"})
    assert r.status_code == 409 and "สาขาแจ้งสนิท" in r.json()["detail"]
    assert level("srinarong", PEPPER).reserved == 2
    assert Order.objects.get(number=n).fulfillment_branch.code == "srinarong"


def test_pickup_orders_cannot_change_branch(place, stocked):
    n = order_for(place, [(NAEM, 1)]).json()["number"]
    assert api_post(stocked, f"/api/admin/orders/{n}/branch", {"branch": "changsanit"}).status_code == 409


# ---------- what customers see ----------
def test_catalog_shows_availability(client, stocked):
    d = client.get("/api/catalog/products/moo-yo-black-pepper").json()
    by = {v["label"]: v["available"] for v in d["variants"]}
    assert by["กลาง"] == 5 and by["เล็ก"] is None and d["in_stock"] is True       # tracked vs not counted
    p = client.get("/api/catalog/products", {"q": "แหนมหมู"}).json()
    assert next(x for x in p if x["slug"] == "naem-pork")["in_stock"] is True


def test_sold_out_product_stays_visible_but_flagged(client, place, stocked):
    ProductVariant.objects.filter(product__slug="moo-yo-black-pepper").exclude(sku=PEPPER).update(is_active=False)
    order_for(place, [(PEPPER, 5)])
    d = client.get("/api/catalog/products/moo-yo-black-pepper").json()
    assert d["in_stock"] is False and d["variants"][0]["available"] == 0


# ---------- unpaid orders expire ----------
def age(number, hours):
    Order.objects.filter(number=number).update(created_at=timezone.now() - timedelta(hours=hours))


def test_unpaid_orders_expire_and_free_their_stock(place, stocked):
    n = order_for(place, [(PEPPER, 3)]).json()["number"]
    age(n, 25)
    out = StringIO()
    call_command("expire_unpaid_orders", stdout=out)
    o = Order.objects.get(number=n)
    assert o.status == "cancelled" and "1" in out.getvalue()
    assert level("srinarong", PEPPER).reserved == 0
    assert o.events.filter(actor="system").exists()


def test_expiry_leaves_fresh_reviewed_and_unquoted_orders_alone(client, place, stocked):
    from tests.test_payments import charge, upload

    fresh = order_for(place, [(NAEM, 1)]).json()["number"]
    quote = order_for(place, [(NAEM, 1)], method="cargo-ubon").json()["number"]
    o = order_for(place, [(NAEM, 1)]).json()
    charge(client, o); upload(client, o)                            # slip under review
    for n in (quote, o["number"]):
        age(n, 100)
    call_command("expire_unpaid_orders", stdout=StringIO())
    assert Order.objects.filter(number__in=[fresh, quote, o["number"]], status="cancelled").count() == 0


# ---------- alerts and reports ----------
def test_low_stock_alert_fires_once_on_crossing(place, stocked, settings):
    settings.LINE_STAFF_IDS = ["Cstaff"]
    settings.LOW_STOCK_THRESHOLD = 3
    Outbox.objects.all().delete()
    order_for(place, [(PEPPER, 1)]); order_for(place, [(PEPPER, 1)])      # 5 -> 4 -> 3: reaches the line
    order_for(place, [(PEPPER, 1)])                                       # 3 -> 2: already low, no second alert
    texts = list(Outbox.objects.filter(kind="low_stock").values_list("text", flat=True))
    assert len(texts) == 1 and "เหลือ 3" in texts[0] and "สาขาศรีณรงค์" in texts[0]


def test_dashboard_counts_low_stock(stocked):
    # pepper@srinarong 5 > 5? no: threshold is 5 so 5 counts as low; naem 5 too; changsanit naem 5
    assert stocked.get("/api/admin/reports/summary").json()["todo"]["low_stock"] == 3
    stock_in(stocked, "srinarong", PEPPER, 10)
    assert stocked.get("/api/admin/reports/summary").json()["todo"]["low_stock"] == 2
