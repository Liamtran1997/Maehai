"""Inventory v2, phase 1: daily online quota, counter sold-out, per-level low-stock line, CSV opening stock,
and the 60-minute hold on unpaid orders."""
from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from maehai.catalog.models import ProductVariant
from maehai.inventory import services
from maehai.inventory.models import OnlineSale, StockLevel, StockMovement
from maehai.notifications.models import Outbox
from maehai.orders.models import Order
from tests.test_inventory import NAEM, PEPPER, adjust, api_post, level, order_for, paid_packing, set_status, stocked  # noqa: F401

from tests.warehouse import stock_in

pytestmark = pytest.mark.django_db
JSON = "application/json"
LEVELS = "/api/admin/inventory/levels"


def put_levels(c, branch="srinarong", sku=PEPPER, **kw):
    return c.put(LEVELS, {"branch": branch, "sku": sku, "online_quota": None, "low_stock_threshold": None, **kw}, content_type=JSON)


def sold_today(branch="srinarong", sku=PEPPER):
    row = OnlineSale.objects.filter(level=level(branch, sku), day=timezone.localdate()).first()
    return row.units if row else 0


# ---------- daily online quota ----------
def test_online_quota_caps_what_the_shop_sells_per_day(place, stocked):
    assert put_levels(stocked, online_quota=3).status_code == 200
    assert order_for(place, [(PEPPER, 2)]).status_code == 201
    r = order_for(place, [(PEPPER, 2)])
    assert r.status_code == 409 and "เหลือ 1" in r.json()["detail"]
    assert order_for(place, [(PEPPER, 1)]).status_code == 201
    assert sold_today() == 3 and level("srinarong", PEPPER).available == 2     # stock is left for the counter
    assert order_for(place, [(PEPPER, 1)]).status_code == 409


def test_shop_availability_follows_the_quota(place, stocked):
    v = ProductVariant.objects.get(sku=PEPPER)
    assert services.available_map([v.id])[v.id] == 5
    put_levels(stocked, online_quota=2)
    assert services.available_map([v.id])[v.id] == 2
    order_for(place, [(PEPPER, 2)])
    assert services.available_map([v.id])[v.id] == 0


def test_quota_unit_returns_when_the_order_is_cancelled_the_same_day(place, stocked):
    put_levels(stocked, online_quota=3)
    n = order_for(place, [(PEPPER, 3)]).json()["number"]
    assert order_for(place, [(PEPPER, 1)]).status_code == 409
    set_status(stocked, n, "cancelled")
    assert sold_today() == 0
    assert order_for(place, [(PEPPER, 3)]).status_code == 201


def test_an_older_days_quota_is_not_handed_back(place, stocked):
    put_levels(stocked, online_quota=3)
    n = order_for(place, [(PEPPER, 3)]).json()["number"]
    from maehai.inventory.models import StockReservation
    StockReservation.objects.update(quota_day=timezone.localdate() - timedelta(days=1))
    set_status(stocked, n, "cancelled")
    assert sold_today() == 3 and level("srinarong", PEPPER).reserved == 0


def test_no_quota_means_stock_is_the_only_limit(place, stocked):
    assert order_for(place, [(PEPPER, 5)]).status_code == 201
    assert not OnlineSale.objects.exists()


def test_quota_and_line_validation(stocked):
    assert put_levels(stocked, online_quota=-1).status_code == 422
    assert put_levels(stocked, branch="nowhere", online_quota=1).status_code == 404
    r = put_levels(stocked, online_quota=4, low_stock_threshold=2).json()
    assert (r["online_quota"], r["low_stock_threshold"], r["low_stock_line"], r["online_available"]) == (4, 2, 2, 4)


# ---------- counter sold-out ----------
def test_sold_out_at_the_counter_stops_online_sales_but_keeps_promised_orders(client, place, stocked):
    n = order_for(place, [(PEPPER, 2)]).json()["number"]
    r = api_post(stocked, "/api/admin/inventory/sold-out", {"branch": "srinarong", "sku": PEPPER})
    assert r.status_code == 200
    lv = level("srinarong", PEPPER)
    assert (lv.on_hand, lv.reserved, lv.available) == (2, 2, 0)
    m = StockMovement.objects.filter(reason="counter_sale").get()
    assert m.delta == -3 and m.on_hand_after == 2
    assert order_for(place, [(PEPPER, 1)]).status_code == 409
    paid_packing(client, stocked, n)
    assert set_status(stocked, n, "done").status_code == 200                          # the order placed earlier is still filled
    assert level("srinarong", PEPPER).on_hand == 0


def test_sold_out_does_nothing_when_nothing_is_free(stocked):
    assert api_post(stocked, "/api/admin/inventory/sold-out", {"branch": "srinarong", "sku": PEPPER}).status_code == 200
    assert api_post(stocked, "/api/admin/inventory/sold-out", {"branch": "srinarong", "sku": PEPPER}).status_code == 200
    assert StockMovement.objects.filter(reason="counter_sale").count() == 1


def test_sold_out_needs_a_counted_item(staff_client, seeded):
    r = api_post(staff_client, "/api/admin/inventory/sold-out", {"branch": "srinarong", "sku": PEPPER})
    assert r.status_code == 409


# ---------- low-stock line per size and branch ----------
@pytest.fixture
def alerts(settings):
    settings.LINE_STAFF_IDS = ["Cstaff"]
    Outbox.objects.all().delete()
    return lambda: list(Outbox.objects.filter(kind="low_stock").values_list("text", flat=True))


def test_each_level_uses_its_own_line(place, stocked, alerts, settings):
    settings.LOW_STOCK_THRESHOLD = 1
    put_levels(stocked, low_stock_threshold=4)
    order_for(place, [(PEPPER, 1)])                       # 5 -> 4: at its own line of 4
    order_for(place, [(NAEM, 1)])                         # naem keeps the shop line of 1: 5 -> 4, no alert
    texts = alerts()
    assert len(texts) == 1 and "เหลือ 4" in texts[0]


def test_alert_comes_from_a_waste_entry_not_only_from_orders(stocked, alerts, settings):
    settings.LOW_STOCK_THRESHOLD = 3
    adjust(stocked, reason="waste", quantity=2)           # 5 -> 3
    assert len(alerts()) == 1
    adjust(stocked, reason="waste", quantity=1)           # already alerted
    assert len(alerts()) == 1


def test_alert_comes_from_a_transfer_out(stocked, alerts, settings):
    settings.LOW_STOCK_THRESHOLD = 3
    r = api_post(stocked, "/api/admin/inventory/documents/transfers",
                 {"to_branch": "changsanit", "vehicle": "กระบะ", "lines": [{"sku": PEPPER, "quantity": 3}]}, content_type=JSON)
    assert r.status_code == 201 and len(alerts()) == 1                # the central warehouse drops to its line


def test_alert_is_sent_again_only_after_stock_was_back_above_the_line(stocked, alerts, settings):
    settings.LOW_STOCK_THRESHOLD = 3
    adjust(stocked, reason="waste", quantity=3)           # 5 -> 2: alert
    adjust(stocked, reason="waste", quantity=1)           # no second one
    assert len(alerts()) == 1
    stock_in(stocked, "srinarong", PEPPER, 10)            # back above the line
    assert level("srinarong", PEPPER).low_alerted is False
    adjust(stocked, reason="waste", quantity=10)          # down again
    assert len(alerts()) == 2


def test_receiving_stock_that_is_still_low_is_not_an_alert(stocked, alerts, settings):
    settings.LOW_STOCK_THRESHOLD = 20
    stock_in(stocked, "srinarong", PEPPER, 1)
    assert alerts() == []


def test_dashboard_low_stock_count_uses_each_levels_line(stocked, settings):
    settings.LOW_STOCK_THRESHOLD = 5
    base = stocked.get("/api/admin/reports/summary").json()["todo"]["low_stock"]
    assert base == 3
    put_levels(stocked, low_stock_threshold=1)            # pepper@srinarong has 5 > 1: no longer low
    assert stocked.get("/api/admin/reports/summary").json()["todo"]["low_stock"] == 2


# ---------- opening stock from CSV ----------
HEADER = "sku,branch_code,tracking,on_hand,online_quota,low_stock_threshold\n"


def preview(c, text):
    return c.post("/api/admin/inventory/import/preview", {"csv": text}, content_type=JSON)


def apply(c, text):
    return c.post("/api/admin/inventory/import/apply", {"csv": text}, content_type=JSON)


def test_template_lists_every_size_at_every_branch(staff_client, seeded):
    t = staff_client.get("/api/admin/inventory/import/template").json()
    lines = t["csv"].lstrip("﻿").strip().splitlines()
    assert lines[0] == HEADER.strip() and t["filename"].endswith(".csv")
    assert f"{PEPPER},srinarong,none,,," in lines and f"{PEPPER},changsanit,none,,," in lines


def test_preview_checks_every_row_and_writes_nothing(staff_client, seeded):
    text = HEADER + "\n".join([
        f"{PEPPER},srinarong,stock,10,4,2",              # ok
        "no-such-sku,srinarong,stock,5,,",               # unknown sku
        f"{NAEM},nowhere,stock,5,,",                     # unknown branch
        f"{NAEM},srinarong,daily,5,,",                   # not in phase 1
        f"{NAEM},srinarong,stock,,,",                    # stock without on_hand
        f"{NAEM},changsanit,none,3,,",                   # none with a number
        f"{PEPPER},srinarong,stock,7,,",                 # duplicate of the first row
        f"{NAEM},srinarong,stock,abc,,",                 # not a number
    ])
    r = preview(staff_client, text)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 8 and body["ok_count"] == 1 and body["error_count"] == 7
    assert body["rows"][0]["errors"] == [] and body["rows"][0]["delta"] == 10
    assert any("ไม่พบ SKU" in e for e in body["rows"][1]["errors"])
    assert any("ไม่พบสาขา" in e for e in body["rows"][2]["errors"])
    assert any("ยังไม่รองรับ" in e for e in body["rows"][3]["errors"])
    assert any("on_hand" in e for e in body["rows"][4]["errors"])
    assert any("ว่างไว้" in e for e in body["rows"][5]["errors"])
    assert any("ซ้ำ" in e for e in body["rows"][6]["errors"])
    assert any("on_hand" in e for e in body["rows"][7]["errors"])
    assert StockLevel.objects.count() == 0 and not ProductVariant.objects.filter(track_stock=True).exists()


def test_preview_rejects_a_file_without_the_required_columns(staff_client, seeded):
    r = preview(staff_client, "sku,on_hand\nx,1\n")
    assert r.status_code == 422 and "branch_code" in r.json()["detail"]


def test_apply_turns_tracking_on_and_writes_opening_stock(staff_client, seeded):
    text = HEADER + f"{PEPPER},srinarong,stock,10,4,2\n{PEPPER},changsanit,stock,6,,\n{NAEM},srinarong,none,,,\n"
    r = apply(staff_client, text)
    assert r.status_code == 200 and r.json()["rows"] == 3
    assert ProductVariant.objects.get(sku=PEPPER).track_stock is True
    a, b = level("srinarong", PEPPER), level("changsanit", PEPPER)
    assert (a.on_hand, a.online_quota, a.low_stock_threshold) == (10, 4, 2)
    assert (b.on_hand, b.online_quota, b.low_stock_threshold) == (6, None, None)
    reasons = set(StockMovement.objects.values_list("reason", flat=True))
    assert reasons == {"opening"}
    from maehai.core.models import AuditLog
    assert AuditLog.objects.filter(action="inventory.import", actor="owner").exists()


def test_a_second_file_is_a_count_not_an_opening(staff_client, seeded):
    apply(staff_client, HEADER + f"{PEPPER},srinarong,stock,10,,\n")
    apply(staff_client, HEADER + f"{PEPPER},srinarong,stock,8,,\n")
    assert list(StockMovement.objects.order_by("id").values_list("reason", "delta")) == [("opening", 10), ("count", -2)]
    apply(staff_client, HEADER + f"{PEPPER},srinarong,stock,8,,\n")           # nothing changed: nothing written
    assert StockMovement.objects.count() == 2


def test_apply_refuses_the_whole_file_when_any_row_is_wrong(staff_client, seeded):
    text = HEADER + f"{PEPPER},srinarong,stock,10,,\nno-such-sku,srinarong,stock,5,,\n"
    r = apply(staff_client, text)
    assert r.status_code == 422 and "1 แถว" in r.json()["detail"]
    assert StockLevel.objects.count() == 0 and not ProductVariant.objects.filter(track_stock=True).exists()


def test_import_cannot_set_stock_below_what_orders_already_hold(place, stocked, staff_client):
    order_for(place, [(PEPPER, 4)])
    r = preview(staff_client, HEADER + f"{PEPPER},srinarong,stock,3,,\n")
    assert r.json()["rows"][0]["errors"] == ["on_hand ต่ำกว่าที่จองไว้ (4)"]
    assert apply(staff_client, HEADER + f"{PEPPER},srinarong,stock,3,,\n").status_code == 422


def test_tracking_none_turns_counting_off(stocked, staff_client):
    r = apply(staff_client, HEADER + f"{PEPPER},srinarong,none,,,\n{PEPPER},changsanit,none,,,\n")
    assert r.status_code == 200 and ProductVariant.objects.get(sku=PEPPER).track_stock is False


def test_template_round_trips_unchanged(stocked, staff_client):
    put_levels(stocked, online_quota=3, low_stock_threshold=2)
    before = list(StockMovement.objects.values_list("id", flat=True))
    csv_text = staff_client.get("/api/admin/inventory/import/template").json()["csv"]
    assert preview(staff_client, csv_text).json()["error_count"] == 0
    assert apply(staff_client, csv_text).status_code == 200
    assert list(StockMovement.objects.values_list("id", flat=True)) == before
    assert level("srinarong", PEPPER).online_quota == 3


def test_only_inventory_adjusters_can_import(client, seeded):
    from tests.conftest import login_as, make_staff
    make_staff("clerk", "sales")
    c = login_as("clerk")
    assert c.get("/api/admin/inventory/import/template").status_code == 403
    assert preview(c, HEADER).status_code == 403
    assert apply(c, HEADER).status_code == 403


# ---------- unpaid orders are held for 60 minutes ----------
def age_minutes(number, minutes):
    Order.objects.filter(number=number).update(created_at=timezone.now() - timedelta(minutes=minutes))


def test_unpaid_order_is_released_after_the_hold(place, stocked, settings):
    settings.ORDER_UNPAID_EXPIRY_MINUTES = 60
    young = order_for(place, [(NAEM, 1)]).json()["number"]
    old = order_for(place, [(PEPPER, 3)]).json()["number"]
    age_minutes(young, 59)
    age_minutes(old, 61)
    call_command("expire_unpaid_orders", stdout=StringIO())
    assert Order.objects.get(number=old).status == "cancelled" and level("srinarong", PEPPER).reserved == 0
    assert Order.objects.get(number=young).status == "waiting_payment"


def test_the_hold_can_be_set_on_the_command_line(place, stocked):
    n = order_for(place, [(NAEM, 1)]).json()["number"]
    age_minutes(n, 20)
    call_command("expire_unpaid_orders", "--minutes", "15", stdout=StringIO())
    assert Order.objects.get(number=n).status == "cancelled"


def test_scheduler_checks_every_five_minutes():
    from maehai.core.management.commands.run_scheduler import JOBS
    assert dict(JOBS)["expire_unpaid_orders"] == 5


@pytest.mark.django_db(transaction=True)
def test_concurrent_orders_cannot_overspend_the_daily_quota(seeded, staff_client, order_payload):
    """Eight customers each order one unit at the same instant against a quota of three. Exactly three may win.
    Runs on Postgres only: SQLite serialises writers by itself and cannot reproduce the race."""
    import threading

    from django.db import connection, connections
    from django.test import Client

    if connection.vendor != "postgresql":
        pytest.skip("row locks need Postgres")
    ProductVariant.objects.filter(sku=PEPPER).update(track_stock=True)
    stock_in(staff_client, "srinarong", PEPPER, 20)
    put_levels(staff_client, online_quota=3)
    results, barrier = [], threading.Barrier(8)

    def go(i):
        try:
            barrier.wait()
            payload = order_payload(items=[{"sku": PEPPER, "quantity": 1}], phone=f"081000000{i}")
            results.append(Client().post("/api/orders", payload, content_type=JSON).status_code)
        finally:
            connections.close_all()

    threads = [threading.Thread(target=go, args=(i,)) for i in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert sorted(results) == [201] * 3 + [409] * 5, results
    assert sold_today() == 3 and level("srinarong", PEPPER).reserved == 3
