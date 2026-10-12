import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client

from maehai.catalog.models import Category, Product

pytestmark = pytest.mark.django_db


@pytest.fixture
def seeded():
    call_command("seed_catalog")


def payload(**over):
    base = {
        "category_slug": "moo-yo", "slug": "test-product", "name": "ทดสอบ",
        "variants": [{"label": "เล็ก", "sku": "t-1", "price_satang": 5000}],
    }
    return {**base, **over}


@pytest.fixture
def staff_client():
    User = get_user_model()
    User.objects.create_user("owner", password="pw-test-123", is_staff=True)
    c = Client(enforce_csrf_checks=False)
    assert c.post("/api/auth/login", {"username": "owner", "password": "pw-test-123"}, content_type="application/json").status_code == 200
    return c


def test_seed_is_idempotent(seeded):
    n = Product.objects.count()
    call_command("seed_catalog")
    assert Product.objects.count() == n == 22


def test_public_list_filters_and_price_from(client, seeded):
    r = client.get("/api/catalog/products", {"category": "moo-yo"})
    assert r.status_code == 200
    items = r.json()
    assert {i["category"]["slug"] for i in items} == {"moo-yo"}
    pepper = next(i for i in items if i["slug"] == "moo-yo-black-pepper")
    assert pepper["price_from_satang"] == 6000  # cheapest size


def test_public_detail_has_variants_and_hides_inactive(client, seeded):
    d = client.get("/api/catalog/products/moo-yo-black-pepper").json()
    assert [v["label"] for v in d["variants"]] == ["เล็ก", "กลาง", "ใหญ่"]
    Product.objects.filter(slug="moo-yo-black-pepper").update(is_active=False)
    assert client.get("/api/catalog/products/moo-yo-black-pepper").status_code == 404
    assert "moo-yo-black-pepper" not in [i["slug"] for i in client.get("/api/catalog/products").json()]


def test_search_by_name(client, seeded):
    names = [i["name"] for i in client.get("/api/catalog/products", {"q": "แหนม"}).json()]
    assert names and all("แหนม" in n for n in names)


def test_admin_requires_staff(client, seeded):
    assert client.get("/api/admin/catalog/products").status_code == 401
    User = get_user_model()
    User.objects.create_user("cust", password="pw-test-123")
    client.post("/api/auth/login", {"username": "cust", "password": "pw-test-123"}, content_type="application/json")
    assert client.get("/api/admin/catalog/products").status_code == 401


def test_admin_create_update_archive(staff_client, seeded):
    r = staff_client.post("/api/admin/catalog/products", payload(), content_type="application/json")
    assert r.status_code == 201
    pid = r.json()["id"]
    assert r.json()["price_from_satang"] == 5000

    # update: change price, add a size, drop none
    body = payload(variants=[
        {"label": "เล็ก", "sku": "t-1", "price_satang": 5500},
        {"label": "กลาง", "sku": "t-2", "price_satang": 9000},
    ])
    r = staff_client.put(f"/api/admin/catalog/products/{pid}", body, content_type="application/json")
    assert r.status_code == 200 and r.json()["price_from_satang"] == 5500 and len(r.json()["variants"]) == 2

    # removing a size deactivates it rather than deleting it
    r = staff_client.put(f"/api/admin/catalog/products/{pid}", payload(), content_type="application/json")
    assert [v["sku"] for v in r.json()["variants"]] == ["t-1"]
    assert Product.objects.get(pk=pid).variants.filter(sku="t-2", is_active=False).exists()

    assert staff_client.delete(f"/api/admin/catalog/products/{pid}").status_code == 204
    assert Product.objects.get(pk=pid).is_active is False


@pytest.mark.parametrize("bad", [
    {"price_satang": 0},            # price must be positive
    {"sku": ""},                    # sku required
])
def test_admin_rejects_bad_variant(staff_client, seeded, bad):
    v = {"label": "เล็ก", "sku": "t-1", "price_satang": 5000, **bad}
    r = staff_client.post("/api/admin/catalog/products", payload(variants=[v]), content_type="application/json")
    assert r.status_code == 422


def test_admin_rejects_unknown_category_band_and_dup_slug(staff_client, seeded):
    post = lambda **o: staff_client.post("/api/admin/catalog/products", payload(**o), content_type="application/json")
    assert post(category_slug="nope").status_code == 422
    assert post(bands=["purple"]).status_code == 422
    assert post().status_code == 201
    assert post().status_code == 409


def test_admin_categories_include_empty_ones(staff_client, seeded):
    Category.objects.create(name="ใหม่", slug="new-empty")
    slugs = [c["slug"] for c in staff_client.get("/api/admin/catalog/categories").json()]
    assert "new-empty" in slugs
    public = [c["slug"] for c in staff_client.get("/api/catalog/categories").json()]
    assert "new-empty" not in public
