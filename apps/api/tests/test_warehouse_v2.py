"""Warehouse v2: central warehouse, slips (IN/TR/RT), materials, branch managers and reconciliation.

These tests describe what the business agreed (docs/specs/inventory.md, decisions D1-D34). Each test is one rule."""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from maehai.catalog.models import ProductVariant
from maehai.core.models import StaffProfile
from maehai.inventory.models import Branch, Document, DocumentLine, MaterialLevel, MaterialMovement, Source, StockLevel, StockMovement
from maehai.notifications.models import Outbox
from tests.conftest import login_as, make_staff
from tests.warehouse import send_and_confirm, stock_in

pytestmark = pytest.mark.django_db
JSON = "application/json"
PEPPER, NAEM = "moo-yo-black-pepper-2", "naem-pork-1"
CENTRAL, CHANGSANIT, BUNGWAI = "srinarong", "changsanit", "bungwai"


@pytest.fixture
def warehouse(seeded, staff_client, settings):
    """Central warehouse plus two stores. Tracked pepper and naem, a source, and a material."""
    settings.LINE_STAFF_IDS = ["Cshared"]
    ProductVariant.objects.filter(sku__in=[PEPPER, NAEM]).update(track_stock=True)
    Source.objects.create(name="ฟาร์ม A", kind="buy")
    return staff_client


def on_hand(branch, sku):
    lv = StockLevel.objects.filter(branch__code=branch, variant__sku=sku).first()
    return lv.on_hand if lv else 0


def mat_on_hand(branch, code):
    ml = MaterialLevel.objects.filter(branch__code=branch, material__code=code).first()
    return ml.on_hand if ml else Decimal(0)


def post(c, url, body):
    return c.post(url, body, content_type=JSON)


def source_id():
    return Source.objects.get(name="ฟาร์ม A").id


def make_manager(username, branch_code, role="branch_manager"):
    make_staff(username, role)
    p = StaffProfile.objects.get(user__username=username)
    p.branches.set([Branch.objects.get(code=branch_code)])
    return login_as(username)


def make_role(username, role, branch_codes=()):
    make_staff(username, role)
    p = StaffProfile.objects.get(user__username=username)
    p.branches.set(list(Branch.objects.filter(code__in=branch_codes)))
    return login_as(username)


# ---------------------------------------------------------------- receipts into the central warehouse (IN-)

def test_a_receipt_puts_stock_into_the_central_warehouse_with_a_number(warehouse):
    r = post(warehouse, "/api/admin/inventory/documents/receipts",
             {"source_id": source_id(), "supplier_ref": "INV-77", "lines": [{"sku": PEPPER, "quantity": 12}]})
    assert r.status_code == 201, r.content
    doc = r.json()
    assert doc["number"].startswith("IN-") and doc["status"] == "posted" and doc["source"] == "ฟาร์ม A"
    assert on_hand(CENTRAL, PEPPER) == 12
    mv = StockMovement.objects.get(variant__sku=PEPPER, reason="receive")
    assert mv.document.number == doc["number"] and mv.actor == "owner"


def test_receipts_only_go_to_the_central_warehouse(warehouse):
    # The API has no branch field on purpose: a receipt can never land anywhere else.
    r = post(warehouse, "/api/admin/inventory/documents/receipts", {"source_id": source_id(), "branch": CHANGSANIT,
                                                                   "lines": [{"sku": PEPPER, "quantity": 1}]})
    assert on_hand(CHANGSANIT, PEPPER) == 0 and on_hand(CENTRAL, PEPPER) == 1
    assert r.status_code == 201


def test_a_size_that_is_not_counted_cannot_be_received(warehouse):
    ProductVariant.objects.filter(sku=PEPPER).update(track_stock=False)
    r = post(warehouse, "/api/admin/inventory/documents/receipts", {"source_id": source_id(), "lines": [{"sku": PEPPER, "quantity": 1}]})
    assert r.status_code == 409 and "เปิดนับสต็อก" in r.json()["detail"]


def test_a_sellable_size_is_whole_numbers_only(warehouse):
    r = post(warehouse, "/api/admin/inventory/documents/receipts", {"source_id": source_id(), "lines": [{"sku": PEPPER, "quantity": 1.5}]})
    assert r.status_code == 422 and "จำนวนเต็ม" in r.json()["detail"]


def test_a_hidden_source_cannot_be_used(warehouse):
    Source.objects.filter(name="ฟาร์ม A").update(is_active=False)
    r = post(warehouse, "/api/admin/inventory/documents/receipts", {"source_id": source_id(), "lines": [{"sku": PEPPER, "quantity": 1}]})
    assert r.status_code == 422


def test_duplicate_items_in_one_slip_are_refused(warehouse):
    r = post(warehouse, "/api/admin/inventory/documents/receipts",
             {"source_id": source_id(), "lines": [{"sku": PEPPER, "quantity": 1}, {"sku": PEPPER, "quantity": 2}]})
    assert r.status_code == 422 and on_hand(CENTRAL, PEPPER) == 0


# ---------------------------------------------------------------- transfers (TR-)

def test_a_transfer_leaves_the_central_warehouse_and_waits_on_the_truck(warehouse):
    stock_in(warehouse, CENTRAL, PEPPER, 10)
    r = post(warehouse, "/api/admin/inventory/documents/transfers",
             {"to_branch": CHANGSANIT, "vehicle": "กระบะ ขาว กข-1234", "carrier": "สมชาย",
              "lines": [{"sku": PEPPER, "quantity": 4}]})
    assert r.status_code == 201, r.content
    assert r.json()["number"].startswith("TR-") and r.json()["status"] == "sent"
    assert (on_hand(CENTRAL, PEPPER), on_hand(CHANGSANIT, PEPPER)) == (6, 0)


def test_the_branch_receives_only_when_it_confirms(warehouse):
    stock_in(warehouse, CENTRAL, PEPPER, 10)
    doc = post(warehouse, "/api/admin/inventory/documents/transfers",
               {"to_branch": CHANGSANIT, "vehicle": "กระบะ", "lines": [{"sku": PEPPER, "quantity": 4}]}).json()
    r = post(warehouse, f"/api/admin/inventory/documents/{doc['number']}/receive",
             {"lines": [{"line_id": doc["lines"][0]["id"], "received": 4}], "substitute_reason": "ทดสอบ"})
    assert r.status_code == 200 and r.json()["status"] == "received_full"
    assert on_hand(CHANGSANIT, PEPPER) == 4


def test_transfer_needs_a_vehicle_and_a_store_destination(warehouse):
    stock_in(warehouse, CENTRAL, PEPPER, 5)
    assert post(warehouse, "/api/admin/inventory/documents/transfers",
                {"to_branch": CHANGSANIT, "vehicle": " ", "lines": [{"sku": PEPPER, "quantity": 1}]}).status_code == 422
    assert post(warehouse, "/api/admin/inventory/documents/transfers",
                {"to_branch": CENTRAL, "vehicle": "x", "lines": [{"sku": PEPPER, "quantity": 1}]}).status_code == 422


def test_a_transfer_cannot_send_more_than_the_central_warehouse_can_give(warehouse):
    stock_in(warehouse, CENTRAL, PEPPER, 3)
    r = post(warehouse, "/api/admin/inventory/documents/transfers",
             {"to_branch": CHANGSANIT, "vehicle": "x", "lines": [{"sku": PEPPER, "quantity": 4}]})
    assert r.status_code == 409 and "มีให้ส่งได้แค่ 3" in r.json()["detail"] and on_hand(CENTRAL, PEPPER) == 3


def test_the_creator_can_cancel_a_slip_nobody_received(warehouse):
    stock_in(warehouse, CENTRAL, PEPPER, 10)
    doc = post(warehouse, "/api/admin/inventory/documents/transfers",
               {"to_branch": CHANGSANIT, "vehicle": "x", "lines": [{"sku": PEPPER, "quantity": 4}]}).json()
    r = post(warehouse, f"/api/admin/inventory/documents/{doc['number']}/cancel", {"reason": "รถเสีย"})
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    assert on_hand(CENTRAL, PEPPER) == 10
    assert StockMovement.objects.filter(reason="transfer_cancel", document__number=doc["number"]).exists()


def test_a_cancelled_or_confirmed_slip_cannot_be_confirmed_again(warehouse):
    stock_in(warehouse, CENTRAL, PEPPER, 10)
    doc = post(warehouse, "/api/admin/inventory/documents/transfers",
               {"to_branch": CHANGSANIT, "vehicle": "x", "lines": [{"sku": PEPPER, "quantity": 4}]}).json()
    post(warehouse, f"/api/admin/inventory/documents/{doc['number']}/cancel", {"reason": "ยกเลิก"})
    r = post(warehouse, f"/api/admin/inventory/documents/{doc['number']}/receive",
             {"lines": [{"line_id": doc["lines"][0]["id"], "received": 4}], "substitute_reason": "x"})
    assert r.status_code == 409 and on_hand(CHANGSANIT, PEPPER) == 0


# ---------------------------------------------------------------- refused goods and lost goods

def test_refused_goods_come_back_on_a_return_slip_and_only_re_enter_when_the_centre_restocks(warehouse):
    stock_in(warehouse, CENTRAL, PEPPER, 10)
    doc = post(warehouse, "/api/admin/inventory/documents/transfers",
               {"to_branch": CHANGSANIT, "vehicle": "x", "lines": [{"sku": PEPPER, "quantity": 4}]}).json()
    r = post(warehouse, f"/api/admin/inventory/documents/{doc['number']}/receive",
             {"lines": [{"line_id": doc["lines"][0]["id"], "received": 3, "reason": "damaged", "note": "แตก 1 แพ็ค"}],
              "substitute_reason": "ทดสอบ"})
    assert r.status_code == 200 and r.json()["status"] == "received_partial"
    assert on_hand(CHANGSANIT, PEPPER) == 3                                  # the refused one never reached the shelf
    back = Document.objects.get(origin__number=doc["number"])
    assert back.kind == "return" and back.status == "sent_back" and back.number.startswith("RT-")
    assert back.lines.get().sent == 1
    ret = post(warehouse, f"/api/admin/inventory/documents/{back.number}/receive-return",
               {"lines": [{"line_id": back.lines.get().id, "restock": 1, "discard": 0}]})
    assert ret.status_code == 200 and ret.json()["status"] == "closed"
    assert on_hand(CENTRAL, PEPPER) == 7                                     # 6 left + 1 back on the shelf


def test_a_refused_item_that_is_thrown_away_leaves_no_stock_behind(warehouse):
    stock_in(warehouse, CENTRAL, PEPPER, 10)
    doc = post(warehouse, "/api/admin/inventory/documents/transfers",
               {"to_branch": CHANGSANIT, "vehicle": "x", "lines": [{"sku": PEPPER, "quantity": 2}]}).json()
    post(warehouse, f"/api/admin/inventory/documents/{doc['number']}/receive",
         {"lines": [{"line_id": doc["lines"][0]["id"], "received": 0, "reason": "wrong"}], "substitute_reason": "ทดสอบ"})
    back = Document.objects.get(origin__number=doc["number"])
    post(warehouse, f"/api/admin/inventory/documents/{back.number}/receive-return",
         {"lines": [{"line_id": back.lines.get().id, "restock": 0, "discard": 2}]})
    assert on_hand(CENTRAL, PEPPER) == 8                                     # 10 - 2 sent, nothing returned to stock
    assert back.lines.get().discarded == 2


def test_a_shortfall_with_no_reason_is_refused_and_nothing_moves(warehouse):
    stock_in(warehouse, CENTRAL, PEPPER, 10)
    doc = post(warehouse, "/api/admin/inventory/documents/transfers",
               {"to_branch": CHANGSANIT, "vehicle": "x", "lines": [{"sku": PEPPER, "quantity": 4}]}).json()
    r = post(warehouse, f"/api/admin/inventory/documents/{doc['number']}/receive",
             {"lines": [{"line_id": doc["lines"][0]["id"], "received": 3}], "substitute_reason": "ทดสอบ"})
    assert r.status_code == 422 and on_hand(CHANGSANIT, PEPPER) == 0
    assert Document.objects.filter(kind="return").count() == 0


def test_a_missing_item_is_recorded_as_lost_and_does_not_come_back(warehouse):
    stock_in(warehouse, CENTRAL, PEPPER, 10)
    doc = post(warehouse, "/api/admin/inventory/documents/transfers",
               {"to_branch": CHANGSANIT, "vehicle": "x", "lines": [{"sku": PEPPER, "quantity": 4}]}).json()
    r = post(warehouse, f"/api/admin/inventory/documents/{doc['number']}/receive",
             {"lines": [{"line_id": doc["lines"][0]["id"], "received": 3, "reason": "missing"}], "substitute_reason": "ทดสอบ"})
    assert r.status_code == 200
    assert not Document.objects.filter(kind="return").exists()              # nothing to send back
    line = DocumentLine.objects.get(document__number=doc["number"])
    assert line.missing == 1 and on_hand(CHANGSANIT, PEPPER) == 3


def test_the_discrepancy_goes_to_the_central_group_too(warehouse):
    stock_in(warehouse, CENTRAL, PEPPER, 10)
    doc = post(warehouse, "/api/admin/inventory/documents/transfers",
               {"to_branch": CHANGSANIT, "vehicle": "x", "lines": [{"sku": PEPPER, "quantity": 4}]}).json()
    Outbox.objects.all().delete()
    post(warehouse, f"/api/admin/inventory/documents/{doc['number']}/receive",
         {"lines": [{"line_id": doc["lines"][0]["id"], "received": 3, "reason": "missing"}], "substitute_reason": "ทดสอบ"})
    assert Outbox.objects.filter(kind="transfer_discrepancy").exists()


# ---------------------------------------------------------------- who may do what, where

def test_a_branch_manager_confirms_their_own_branch_only(warehouse):
    stock_in(warehouse, CENTRAL, PEPPER, 10)
    send = post(warehouse, "/api/admin/inventory/documents/transfers",
                {"to_branch": CHANGSANIT, "vehicle": "x", "lines": [{"sku": PEPPER, "quantity": 4}]}).json()
    bungwai_send = post(warehouse, "/api/admin/inventory/documents/transfers",
                        {"to_branch": BUNGWAI, "vehicle": "x", "lines": [{"sku": PEPPER, "quantity": 2}]}).json()
    mgr = make_manager("mgr-changsanit", CHANGSANIT)
    assert mgr.get(f"/api/admin/inventory/documents/{bungwai_send['number']}").status_code == 404
    other = post(mgr, f"/api/admin/inventory/documents/{bungwai_send['number']}/receive",
                 {"lines": [{"line_id": bungwai_send["lines"][0]["id"], "received": 2}]})
    assert other.status_code in (403, 404)
    r = post(mgr, f"/api/admin/inventory/documents/{send['number']}/receive",
             {"lines": [{"line_id": send["lines"][0]["id"], "received": 4}]})
    assert r.status_code == 200 and r.json()["substitute_reason"] == ""       # own manager: no reason needed
    assert on_hand(CHANGSANIT, PEPPER) == 4


def test_a_branch_manager_cannot_receive_at_the_centre_or_send_stock(warehouse):
    mgr = make_manager("mgr-bungwai", BUNGWAI)
    assert post(mgr, "/api/admin/inventory/documents/receipts",
                {"source_id": source_id(), "lines": [{"sku": PEPPER, "quantity": 1}]}).status_code == 403
    assert post(mgr, "/api/admin/inventory/documents/transfers",
                {"to_branch": CHANGSANIT, "vehicle": "x", "lines": [{"sku": PEPPER, "quantity": 1}]}).status_code == 403


def test_a_branch_manager_sees_only_their_own_branch_stock(warehouse):
    mgr = make_manager("mgr-changsanit-2", CHANGSANIT)
    assert [b["code"] for b in mgr.get("/api/admin/inventory/branches").json()] == [CHANGSANIT]
    stock_rows = mgr.get("/api/admin/inventory/stock").json()
    assert all(set(l["branch"] for l in row["levels"]) == {CHANGSANIT} for row in stock_rows)


def test_substituting_for_a_branch_needs_a_reason_and_is_recorded(warehouse):
    stock_in(warehouse, CENTRAL, PEPPER, 10)
    doc = post(warehouse, "/api/admin/inventory/documents/transfers",
               {"to_branch": CHANGSANIT, "vehicle": "x", "lines": [{"sku": PEPPER, "quantity": 4}]}).json()
    body = {"lines": [{"line_id": doc["lines"][0]["id"], "received": 4}]}
    assert post(warehouse, f"/api/admin/inventory/documents/{doc['number']}/receive", body).status_code == 422
    body["substitute_reason"] = "ผู้จัดการสาขาไม่อยู่"
    r = post(warehouse, f"/api/admin/inventory/documents/{doc['number']}/receive", body)
    assert r.status_code == 200 and r.json()["substitute_reason"] == "ผู้จัดการสาขาไม่อยู่"


def test_warehouse_staff_send_and_take_back_but_do_not_receive_from_suppliers(warehouse):
    stock_in(warehouse, CENTRAL, PEPPER, 10)
    kho = make_role("kho-central", "warehouse", [CENTRAL])
    assert post(kho, "/api/admin/inventory/documents/receipts",
                {"source_id": source_id(), "lines": [{"sku": PEPPER, "quantity": 1}]}).status_code == 403
    assert post(kho, "/api/admin/inventory/documents/transfers",
                {"to_branch": CHANGSANIT, "vehicle": "x", "lines": [{"sku": PEPPER, "quantity": 1}]}).status_code == 201


def test_only_the_creator_or_a_manager_can_cancel_a_slip(warehouse):
    stock_in(warehouse, CENTRAL, PEPPER, 10)
    doc = post(warehouse, "/api/admin/inventory/documents/transfers",
               {"to_branch": CHANGSANIT, "vehicle": "x", "lines": [{"sku": PEPPER, "quantity": 4}]}).json()
    kho = make_role("kho-cancel", "warehouse", [CENTRAL])
    assert post(kho, f"/api/admin/inventory/documents/{doc['number']}/cancel", {"reason": "ไม่ใช่ของฉัน"}).status_code == 403


def test_a_branch_cannot_be_given_a_branch_manager_role_without_exactly_one_store(warehouse):
    body = {"username": "mgr-none", "display_name": "ไม่มีสาขา", "role": "branch_manager", "password": "Long-enough-pass-77", "branch_codes": []}
    assert warehouse.post("/api/admin/staff", body, content_type=JSON).status_code == 422
    body["branch_codes"] = [CENTRAL]
    assert warehouse.post("/api/admin/staff", {**body, "username": "mgr-c"}, content_type=JSON).status_code == 422
    body["branch_codes"] = [CHANGSANIT]
    assert warehouse.post("/api/admin/staff", {**body, "username": "mgr-ok"}, content_type=JSON).status_code == 201


# ---------------------------------------------------------------- returns a branch makes on its own

def test_a_branch_can_send_surplus_back_and_it_leaves_the_shelf_at_once(warehouse):
    stock_in(warehouse, CENTRAL, PEPPER, 10)
    send_and_confirm(warehouse, CHANGSANIT, [(PEPPER, 5)])
    assert on_hand(CHANGSANIT, PEPPER) == 5
    mgr = make_manager("mgr-return", CHANGSANIT)
    r = post(mgr, "/api/admin/inventory/documents/returns", {"branch": CHANGSANIT, "note": "เกินจากยอดขาย",
                                                              "lines": [{"sku": PEPPER, "quantity": 2}]})
    assert r.status_code == 201 and r.json()["number"].startswith("RT-")
    assert on_hand(CHANGSANIT, PEPPER) == 3
    back = Document.objects.get(number=r.json()["number"])
    post(warehouse, f"/api/admin/inventory/documents/{back.number}/receive-return",
         {"lines": [{"line_id": back.lines.get().id, "restock": 2, "discard": 0}]})
    assert on_hand(CENTRAL, PEPPER) == 7


# ---------------------------------------------------------------- materials and supplies

def test_materials_take_decimals_and_units_and_never_sell_online(warehouse):
    r = post(warehouse, "/api/admin/inventory/materials",
             {"code": "pork-leg", "name": "เนื้อหมู", "kind": "material", "unit": "กก.", "low_stock_threshold": "5"})
    assert r.status_code == 201
    r = post(warehouse, "/api/admin/inventory/documents/receipts",
             {"source_id": source_id(), "lines": [{"material_code": "pork-leg", "quantity": "12.5"}]})
    assert r.status_code == 201, r.content
    assert mat_on_hand(CENTRAL, "pork-leg") == Decimal("12.5")
    assert all(row["sku"] != "pork-leg" for row in warehouse.get("/api/admin/inventory/stock").json())


def test_a_material_quantity_has_at_most_three_decimals(warehouse):
    post(warehouse, "/api/admin/inventory/materials", {"code": "bag", "name": "ถุง", "kind": "supply", "unit": "ใบ"})
    r = post(warehouse, "/api/admin/inventory/documents/receipts",
             {"source_id": source_id(), "lines": [{"material_code": "bag", "quantity": "1.2345"}]})
    assert r.status_code == 422


def test_materials_are_consumed_by_hand_and_cannot_go_negative(warehouse):
    post(warehouse, "/api/admin/inventory/materials", {"code": "leaf", "name": "ใบตอง", "kind": "material", "unit": "กก."})
    post(warehouse, "/api/admin/inventory/documents/receipts",
         {"source_id": source_id(), "lines": [{"material_code": "leaf", "quantity": "10"}]})
    r = post(warehouse, "/api/admin/inventory/materials/adjust",
             {"branch": CENTRAL, "material_code": "leaf", "reason": "consume", "quantity": "10.25"})
    assert r.status_code == 409 and mat_on_hand(CENTRAL, "leaf") == 10
    r = post(warehouse, "/api/admin/inventory/materials/adjust",
             {"branch": CENTRAL, "material_code": "leaf", "reason": "consume", "quantity": "2.25"})
    assert r.status_code == 200 and mat_on_hand(CENTRAL, "leaf") == Decimal("7.75")
    assert MaterialMovement.objects.filter(reason="consume").exists()


def test_a_material_goes_out_and_is_confirmed_like_a_size(warehouse):
    post(warehouse, "/api/admin/inventory/materials", {"code": "box", "name": "กล่อง", "kind": "supply", "unit": "ใบ"})
    post(warehouse, "/api/admin/inventory/documents/receipts",
         {"source_id": source_id(), "lines": [{"material_code": "box", "quantity": "50"}]})
    doc = post(warehouse, "/api/admin/inventory/documents/transfers",
               {"to_branch": CHANGSANIT, "vehicle": "x", "lines": [{"material_code": "box", "quantity": "20"}]}).json()
    assert mat_on_hand(CENTRAL, "box") == 30 and mat_on_hand(CHANGSANIT, "box") == 0
    post(warehouse, f"/api/admin/inventory/documents/{doc['number']}/receive",
         {"lines": [{"line_id": doc["lines"][0]["id"], "received": "20"}], "substitute_reason": "ทดสอบ"})
    assert mat_on_hand(CHANGSANIT, "box") == 20


def test_a_material_unit_cannot_be_changed_once_it_has_moved(warehouse):
    post(warehouse, "/api/admin/inventory/materials", {"code": "wrap", "name": "ฟิล์ม", "kind": "supply", "unit": "ม้วน"})
    post(warehouse, "/api/admin/inventory/documents/receipts",
         {"source_id": source_id(), "lines": [{"material_code": "wrap", "quantity": "2"}]})
    r = warehouse.put("/api/admin/inventory/materials/wrap", {"name": "ฟิล์มยืด", "kind": "supply", "low_stock_threshold": None,
                                                                "note": "", "is_active": True}, content_type=JSON)
    assert r.status_code == 200 and r.json()["unit"] == "ม้วน" and r.json()["in_use"] is True


# ---------------------------------------------------------------- reconciliation

def test_reconciliation_balances_for_every_item_and_shows_goods_on_the_truck(warehouse):
    stock_in(warehouse, CENTRAL, PEPPER, 10)
    send_and_confirm(warehouse, CHANGSANIT, [(PEPPER, 4)])
    doc = post(warehouse, "/api/admin/inventory/documents/transfers",
               {"to_branch": CHANGSANIT, "vehicle": "x", "lines": [{"sku": PEPPER, "quantity": 2}]}).json()
    today = timezone.localdate().isoformat()
    central = warehouse.get("/api/admin/inventory/reports/reconcile", {"branch": CENTRAL, "date_from": today, "date_to": today}).json()
    row = next(r for r in central["rows"] if r["kind"] == "product" and r["name"].startswith("หมูยอพริกไทยดำ (กลาง)"))
    assert row["balanced"] is True
    assert row["flows"]["receive"] == "10" and row["flows"]["transfer_out"] == "-6"
    assert row["in_transit_out"] == "2"                                       # the 2 still on the truck
    store = warehouse.get("/api/admin/inventory/reports/reconcile", {"branch": CHANGSANIT, "date_from": today, "date_to": today}).json()
    srow = next(r for r in store["rows"] if r["name"].startswith("หมูยอพริกไทยดำ (กลาง)"))
    assert srow["balanced"] is True and srow["flows"]["transfer_in"] == "4"
    assert srow["in_transit_in"] == "2"
    assert central["unbalanced"] == 0 and store["unbalanced"] == 0
    assert doc["status"] == "sent"


def test_reconciliation_counts_losses_from_closed_slips(warehouse):
    stock_in(warehouse, CENTRAL, PEPPER, 10)
    doc = post(warehouse, "/api/admin/inventory/documents/transfers",
               {"to_branch": CHANGSANIT, "vehicle": "x", "lines": [{"sku": PEPPER, "quantity": 4}]}).json()
    post(warehouse, f"/api/admin/inventory/documents/{doc['number']}/receive",
         {"lines": [{"line_id": doc["lines"][0]["id"], "received": 3, "reason": "missing"}], "substitute_reason": "ทดสอบ"})
    today = timezone.localdate().isoformat()
    store = warehouse.get("/api/admin/inventory/reports/reconcile", {"branch": CHANGSANIT, "date_from": today, "date_to": today}).json()
    srow = next(r for r in store["rows"] if r["name"].startswith("หมูยอพริกไทยดำ (กลาง)"))
    assert srow["lost"] == "1" and srow["balanced"] is True


def test_reconciliation_rejects_a_range_that_runs_backwards(warehouse):
    r = warehouse.get("/api/admin/inventory/reports/reconcile", {"branch": CENTRAL, "date_from": "2026-10-10", "date_to": "2026-10-01"})
    assert r.status_code == 422


# ---------------------------------------------------------------- alerts

def test_a_slip_nobody_confirms_for_a_day_is_raised_once(warehouse):
    from maehai.inventory.documents import alert_overdue

    stock_in(warehouse, CENTRAL, PEPPER, 10)
    doc = post(warehouse, "/api/admin/inventory/documents/transfers",
               {"to_branch": CHANGSANIT, "vehicle": "x", "lines": [{"sku": PEPPER, "quantity": 4}]}).json()
    Document.objects.filter(number=doc["number"]).update(sent_at=timezone.now() - timedelta(hours=25))
    Outbox.objects.all().delete()
    assert alert_overdue() == 1
    assert alert_overdue() == 0
    assert Outbox.objects.filter(kind="stock_overdue").count() == 1


def test_a_branch_with_its_own_line_group_gets_its_transfers_there(warehouse):
    Branch.objects.filter(code=CHANGSANIT).update(line_group_id="Cchangsanit")
    stock_in(warehouse, CENTRAL, PEPPER, 10)
    Outbox.objects.all().delete()
    post(warehouse, "/api/admin/inventory/documents/transfers",
         {"to_branch": CHANGSANIT, "vehicle": "x", "lines": [{"sku": PEPPER, "quantity": 1}]})
    rows = list(Outbox.objects.filter(kind="transfer_sent").values_list("recipient", flat=True))
    assert rows == ["Cchangsanit"]


def test_a_branch_without_its_own_group_uses_the_shared_one(warehouse):
    stock_in(warehouse, CENTRAL, PEPPER, 10)
    Outbox.objects.all().delete()
    post(warehouse, "/api/admin/inventory/documents/transfers",
         {"to_branch": BUNGWAI, "vehicle": "x", "lines": [{"sku": PEPPER, "quantity": 1}]})
    assert list(Outbox.objects.filter(kind="transfer_sent").values_list("recipient", flat=True)) == ["Cshared"]


def test_bungwai_is_a_store_with_its_own_pickup_method(seeded):
    from maehai.shipping.models import ShippingMethod

    b = Branch.objects.get(code=BUNGWAI)
    assert b.kind == "store" and ShippingMethod.objects.get(code="pickup-bungwai").branch_id == b.id
    assert Branch.objects.get(code=CENTRAL).kind == "central"


def test_the_owner_sets_a_branch_line_group_and_only_approvers_can(warehouse):
    r = warehouse.put(f"/api/admin/inventory/branches/{CHANGSANIT}/line-group", {"line_group_id": "Cabc123"}, content_type=JSON)
    assert r.status_code == 200 and r.json()["line_group_id"] == "Cabc123"
    settings_rows = {b["code"]: b["line_group_id"] for b in warehouse.get("/api/admin/inventory/branches/settings").json()}
    assert settings_rows[CHANGSANIT] == "Cabc123"
    mgr = make_manager("mgr-group", CHANGSANIT)
    assert mgr.put(f"/api/admin/inventory/branches/{CHANGSANIT}/line-group", {"line_group_id": "Cx"}, content_type=JSON).status_code == 403


def test_a_blank_line_group_falls_back_to_the_shared_group(warehouse):
    warehouse.put(f"/api/admin/inventory/branches/{CHANGSANIT}/line-group", {"line_group_id": ""}, content_type=JSON)
    stock_in(warehouse, CENTRAL, PEPPER, 10)
    Outbox.objects.all().delete()
    post(warehouse, "/api/admin/inventory/documents/transfers",
         {"to_branch": CHANGSANIT, "vehicle": "x", "lines": [{"sku": PEPPER, "quantity": 1}]})
    assert list(Outbox.objects.filter(kind="transfer_sent").values_list("recipient", flat=True)) == ["Cshared"]


def test_the_dashboard_counts_slips_waiting_to_be_received(warehouse):
    stock_in(warehouse, CENTRAL, PEPPER, 10)
    post(warehouse, "/api/admin/inventory/documents/transfers",
         {"to_branch": CHANGSANIT, "vehicle": "x", "lines": [{"sku": PEPPER, "quantity": 1}]})
    assert warehouse.get("/api/admin/reports/summary").json()["todo"]["slips_to_receive"] == 1
