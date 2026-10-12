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
    settings.PRIVATE_MEDIA_ROOT = tmp_path / "private"
    settings.PROMPTPAY_ID = "0812345678"
    settings.NON_WORKING_DATES = []


@pytest.fixture
def seeded(db):
    call_command("seed_catalog")
    call_command("seed_shipping")
    call_command("seed_inventory")


def make_staff(username="owner", role="owner", password="pw-test-123", must_change=False):
    from maehai.core.models import StaffProfile

    u = get_user_model().objects.create_user(username, password=password, is_staff=True)
    StaffProfile.objects.create(user=u, role=role, must_change_password=must_change)
    return u


def login_as(username, password="pw-test-123"):
    c = Client()
    r = c.post("/api/auth/login", {"username": username, "password": password}, content_type="application/json")
    assert r.status_code == 200, r.content
    return c


@pytest.fixture
def staff_client(db):
    """Logged in as the owner: can do everything. Role-specific tests use `as_role`."""
    make_staff("owner", "owner")
    return login_as("owner")


@pytest.fixture
def as_role(db):
    """as_role("sales") -> a client logged in as a new staff member with that role."""
    made = {}

    def go(role):
        if role not in made:                      # asking for the same role twice returns the same person
            make_staff(f"user-{role}", role)
            made[role] = login_as(f"user-{role}")
        return made[role]
    return go


@pytest.fixture
def order_payload():
    def make(**over):
        base = {
            "items": [{"sku": "moo-yo-black-pepper-2", "quantity": 1}, {"sku": "naem-pork-1", "quantity": 2}],
            "customer_name": "สมชาย ใจดี", "phone": "081-234-5678", "shipping_method": "pickup-srinarong",
            "requested_date": earliest_fulfillment_date().isoformat(), "accepted_terms": True,
        }
        return {**base, **over}
    return make


@pytest.fixture
def place(client, order_payload, seeded):
    def go(**over):
        return client.post("/api/orders", order_payload(**over), content_type="application/json")
    return go
