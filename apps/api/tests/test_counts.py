"""Stock counts (CNT-) and counter day-close: blind counting, auto-approval under the limit, approver above it,
sending back, and refusing a count that went stale."""
from decimal import Decimal

import pytest

from maehai.catalog.models import ProductVariant
from maehai.core.models import StaffProfile
from maehai.inventory.models import Branch, Material, MaterialLevel, Source, StockLevel, StockMovement
from tests.conftest import login_as, make_staff
from tests.warehouse import stock_in

pytestmark = pytest.mark.django_db
JSON = "application/json"
PEPPER, NAEM = "moo-yo-black-pepper-2", "naem-pork-1"
CENTRAL = "srinarong"


@pytest.fixture
def counting(seeded, staff_client):
    ProductVariant.objects.filter(sku__in=[PEPPER, NAEM]).update(track_stock=True)
    stock_in(staff_client, CENTRAL, PEPPER, 30)
    stock_in(staff_client, CENTRAL, NAEM, 10)
    return staff_client


def on_hand(sku):
    return StockLevel.objects.get(branch__code=CENTRAL, variant__sku=sku).on_hand


def start(c):
    r = c.post("/api/admin/inventory/counts", {"branch": CENTRAL, "note": ""}, content_type=JSON)
    assert r.status_code == 201, r.content
    return r.json()


def line_for(doc, sku):
    return next(l for l in doc["lines"] if l["sku"] == sku)


def enter(c, doc, values):
    lines = [{"line_id": line_for(doc, sku)["id"], "counted": str(q)} for sku, q in values.items()]
    r = c.put(f"/api/admin/inventory/counts/{doc['number']}/lines", {"lines": lines}, content_type=JSON)
    assert r.status_code == 200, r.content
    return r.json()


def submit(c, doc):
    return c.post(f"/api/admin/inventory/counts/{doc['number']}/submit", {}, content_type=JSON)


def test_the_count_lists_every_tracked_size_and_hides_the_expected_figure_from_the_counter(counting):
    doc = start(counting)
    assert doc["number"].startswith("CNT-") and doc["status"] == "counting"
    assert {l["sku"] for l in doc["lines"]} == {PEPPER, NAEM}
    make_staff("clerk-count", "warehouse")
    kho = login_as("clerk-count")                                    # warehouse staff with no branch assigned
    assert kho.get(f"/api/admin/inventory/documents/{doc['number']}").status_code == 404


def test_a_small_difference_is_posted_at_once_by_the_counter(counting):
    doc = start(counting)
    enter(counting, doc, {PEPPER: 28, NAEM: 10})                     # 2 short on pepper
    r = submit(counting, doc)
    assert r.status_code == 200 and r.json()["status"] == "posted"
    assert on_hand(PEPPER) == 28
    mv = StockMovement.objects.get(variant__sku=PEPPER, reason="count")
    assert mv.delta == -2 and mv.document.number == doc["number"]


def test_a_large_difference_waits_for_an_approver(counting):
    doc = start(counting)
    enter(counting, doc, {PEPPER: 5, NAEM: 10})                      # 25 short: over the 20-unit limit
    r = submit(counting, doc)
    assert r.json()["status"] == "pending_approval" and on_hand(PEPPER) == 30    # nothing changed yet
    make_staff("clerk-approve", "warehouse")
    c = login_as("clerk-approve")
    assert c.post(f"/api/admin/inventory/counts/{doc['number']}/approve", {}, content_type=JSON).status_code == 403


def test_the_owner_approves_and_the_stock_follows_the_count(counting):
    doc = start(counting)
    enter(counting, doc, {PEPPER: 5, NAEM: 10})
    submit(counting, doc)
    r = counting.post(f"/api/admin/inventory/counts/{doc['number']}/approve", {}, content_type=JSON)
    assert r.status_code == 200 and r.json()["status"] == "posted"
    assert on_hand(PEPPER) == 5


def test_a_manager_can_send_a_count_back_with_a_reason_and_the_counter_recounts(counting):
    doc = start(counting)
    enter(counting, doc, {PEPPER: 5, NAEM: 10})
    submit(counting, doc)
    r = counting.post(f"/api/admin/inventory/counts/{doc['number']}/reject", {"reason": "นับผิดชั้น"}, content_type=JSON)
    assert r.json()["status"] == "counting" and r.json()["review_note"] == "นับผิดชั้น"
    enter(counting, doc, {PEPPER: 29, NAEM: 10})
    assert submit(counting, doc).json()["status"] == "posted"
    assert on_hand(PEPPER) == 29


def test_a_count_that_is_not_complete_cannot_be_submitted(counting):
    doc = start(counting)
    enter(counting, doc, {PEPPER: 30})
    r = submit(counting, doc)
    assert r.status_code == 422 and "ยังนับไม่ครบ" in r.json()["detail"]


def test_a_count_goes_stale_when_stock_moves_after_it_was_typed(counting):
    doc = start(counting)
    enter(counting, doc, {PEPPER: 30, NAEM: 10})
    stock_in(counting, CENTRAL, PEPPER, 4)                           # a receipt lands mid-count
    r = submit(counting, doc)
    assert r.status_code == 409 and "ต้องนับใหม่" in r.json()["detail"]
    assert on_hand(PEPPER) == 34


def test_a_count_cannot_take_stock_that_orders_already_hold(counting, place):
    order = place(items=[{"sku": PEPPER, "quantity": 20}], shipping_method="pickup-srinarong")
    assert order.status_code == 201
    doc = start(counting)
    enter(counting, doc, {PEPPER: 5, NAEM: 10})                      # 25 short, approved by the owner
    submit(counting, doc)
    r = counting.post(f"/api/admin/inventory/counts/{doc['number']}/approve", {}, content_type=JSON)
    assert r.status_code == 409 and on_hand(PEPPER) == 30


def test_the_counter_cannot_count_a_branch_they_do_not_work_at(counting):
    make_staff("clerk-store", "branch_manager")
    StaffProfile.objects.get(user__username="clerk-store").branches.set(Branch.objects.filter(code="changsanit"))
    c = login_as("clerk-store")
    assert c.post("/api/admin/inventory/counts", {"branch": CENTRAL, "note": ""}, content_type=JSON).status_code == 403


def test_materials_are_counted_with_decimals(counting):
    m = Material.objects.create(code="pork-leg", name="เนื้อหมู", kind="material", unit="กก.")
    src = Source.objects.create(name="ต้นทาง", kind="buy")
    r = counting.post("/api/admin/inventory/documents/receipts",
                      {"source_id": src.id, "lines": [{"material_code": "pork-leg", "quantity": "12.5"}]}, content_type=JSON)
    assert r.status_code == 201
    doc = start(counting)
    lines = [{"line_id": l["id"], "counted": "12.25"} for l in doc["lines"] if l["material_code"] == "pork-leg"]
    counting.put(f"/api/admin/inventory/counts/{doc['number']}/lines", {"lines": lines}, content_type=JSON)
    rest = [{"line_id": l["id"], "counted": "30" if l["sku"] == PEPPER else "10"} for l in doc["lines"] if l["sku"]]
    counting.put(f"/api/admin/inventory/counts/{doc['number']}/lines", {"lines": rest}, content_type=JSON)
    assert submit(counting, doc).json()["status"] == "posted"
    assert MaterialLevel.objects.get(branch__code=CENTRAL, material=m).on_hand == Decimal("12.250")


def test_the_counter_sees_no_expected_figure_but_the_approver_does(counting):
    doc = start(counting)
    filled = enter(counting, doc, {PEPPER: 30, NAEM: 10})
    assert all(l["expected"] is not None for l in filled["lines"])   # the owner is an approver
    doc_plain = counting.get(f"/api/admin/inventory/documents/{doc['number']}").json()
    assert all("expected" in l for l in doc_plain["lines"])


# ---------------------------------------------------------------- counter day-close

def day_close(c, sales):
    return c.post(f"/api/admin/inventory/branches/{CENTRAL}/day-close", {"branch": CENTRAL, "lines": sales}, content_type=JSON)


def test_day_close_takes_counter_sales_off_the_shelf(counting):
    r = day_close(counting, [{"sku": PEPPER, "sold": 7}])
    assert r.status_code == 200
    assert on_hand(PEPPER) == 23
    assert StockMovement.objects.filter(reason="counter_sale", delta=-7).exists()


def test_day_close_cannot_sell_more_than_is_free(counting, place):
    place(items=[{"sku": PEPPER, "quantity": 25}], shipping_method="pickup-srinarong")
    r = day_close(counting, [{"sku": PEPPER, "sold": 10}])
    assert r.status_code == 409 and "มีให้ส่งได้แค่ 5" in r.json()["detail"]
    assert on_hand(PEPPER) == 30


def test_day_close_with_zero_sales_changes_nothing(counting):
    assert day_close(counting, [{"sku": PEPPER, "sold": 0}]).json()["lines"] == []
    assert on_hand(PEPPER) == 30
