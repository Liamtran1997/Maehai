"""The stock table shows what is on its way between branches, until the receiving branch confirms it."""
import pytest

from maehai.catalog.models import ProductVariant
from maehai.inventory.models import Branch
from tests.warehouse import CENTRAL, JSON, send_and_confirm, stock_in

pytestmark = pytest.mark.django_db
SKU = "moo-yo-black-pepper-2"


def tracked(sku=SKU):
    ProductVariant.objects.filter(sku=sku).update(track_stock=True)


def row(client, sku=SKU):
    return next(r for r in client.get("/api/admin/inventory/stock").json() if r["sku"] == sku)


def test_sent_but_unconfirmed_stock_is_in_transit(staff_client, seeded):
    tracked()
    stock_in(staff_client, CENTRAL, SKU, 20)
    branch = Branch.objects.exclude(code=CENTRAL).filter(is_active=True).first().code
    r = staff_client.post("/api/admin/inventory/documents/transfers",
                          {"to_branch": branch, "vehicle": "ทดสอบ", "lines": [{"sku": SKU, "quantity": 7}]}, content_type=JSON)
    assert r.status_code == 201, r.content
    assert row(staff_client)["in_transit"] == 7


def test_confirmed_stock_is_no_longer_in_transit(staff_client, seeded):
    tracked()
    stock_in(staff_client, CENTRAL, SKU, 20)
    branch = Branch.objects.exclude(code=CENTRAL).filter(is_active=True).first().code
    send_and_confirm(staff_client, branch, [(SKU, 5)])
    assert row(staff_client)["in_transit"] == 0


def test_a_size_with_nothing_moving_reports_zero(staff_client, seeded):
    assert row(staff_client)["in_transit"] == 0
