import pytest

from maehai.catalog.models import PriceChange, Product, ProductVariant

pytestmark = pytest.mark.django_db
JSON = "application/json"


def body_for(product, **price_by_label):
    variants = [{"label": v.label, "sku": v.sku, "price_satang": price_by_label.get(v.label, v.price_satang)}
                for v in product.variants.order_by("sort_order")]
    return {"category_slug": product.category.slug, "slug": product.slug, "name": product.name, "variants": variants}


def test_a_price_change_is_recorded_with_old_new_and_who(staff_client, seeded):
    p = Product.objects.get(slug="moo-yo-black-pepper")
    r = staff_client.put(f"/api/admin/catalog/products/{p.id}", body_for(p, กลาง=9000), content_type=JSON)
    assert r.status_code == 200
    change = PriceChange.objects.get(variant__sku="moo-yo-black-pepper-2", old_price_satang=8500)
    assert change.new_price_satang == 9000 and change.actor == "owner"


def test_unchanged_prices_record_nothing(staff_client, seeded):
    p = Product.objects.get(slug="moo-yo-black-pepper")
    staff_client.put(f"/api/admin/catalog/products/{p.id}", body_for(p), content_type=JSON)
    assert PriceChange.objects.count() == 0


def test_new_size_is_recorded_as_a_first_price(staff_client, seeded):
    p = Product.objects.get(slug="naem-pork")
    body = body_for(p)
    body["variants"].append({"label": "พิเศษ", "sku": "naem-special", "price_satang": 7000})
    staff_client.put(f"/api/admin/catalog/products/{p.id}", body, content_type=JSON)
    c = PriceChange.objects.get(variant__sku="naem-special")
    assert c.old_price_satang is None and c.new_price_satang == 7000


def test_history_endpoint_lists_newest_first_and_needs_pricing_permission(staff_client, as_role, seeded):
    p = Product.objects.get(slug="moo-yo-black-pepper")
    staff_client.put(f"/api/admin/catalog/products/{p.id}", body_for(p, กลาง=9000), content_type=JSON)
    staff_client.put(f"/api/admin/catalog/products/{p.id}", body_for(p, กลาง=9500), content_type=JSON)
    rows = staff_client.get(f"/api/admin/catalog/products/{p.id}/price-history").json()
    middle = [r for r in rows if r["sku"] == "moo-yo-black-pepper-2"]
    assert [(r["old_price_satang"], r["new_price_satang"]) for r in middle] == [(9000, 9500), (8500, 9000)]
    assert as_role("content").get(f"/api/admin/catalog/products/{p.id}/price-history").status_code == 403
    assert as_role("manager").get(f"/api/admin/catalog/products/{p.id}/price-history").status_code == 200
