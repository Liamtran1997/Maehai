import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client

from maehai.shipping.schedule import earliest_fulfillment_date


@pytest.fixture(autouse=True)
def _isolate(settings, tmp_path):
    from django.core.cache import cache

    cache.clear()
    settings.RATE_LIMIT_ENABLED = False   # most tests place many orders from one address; rate limit tests switch it on
    settings.MEDIA_ROOT = tmp_path
    settings.PROMPTPAY_ID = "0812345678"
    settings.NON_WORKING_DATES = []


@pytest.fixture
def seeded(db):
    call_command("seed_catalog")
    call_command("seed_shipping")
    call_command("seed_inventory")


@pytest.fixture
def staff_client(db):
    get_user_model().objects.create_user("owner", password="pw-test-123", is_staff=True)
    c = Client()
    r = c.post("/api/auth/login", {"username": "owner", "password": "pw-test-123"}, content_type="application/json")
    assert r.status_code == 200
    return c


@pytest.fixture
def order_payload():
    def make(**over):
        base = {
            "items": [{"sku": "moo-yo-black-pepper-2", "quantity": 1}, {"sku": "naem-pork-1", "quantity": 2}],
            "customer_name": "สมชาย ใจดี", "phone": "081-234-5678", "shipping_method": "pickup-srinarong",
            "requested_date": earliest_fulfillment_date().isoformat(),
        }
        return {**base, **over}
    return make


@pytest.fixture
def place(client, order_payload, seeded):
    def go(**over):
        return client.post("/api/orders", order_payload(**over), content_type="application/json")
    return go
