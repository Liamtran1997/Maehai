from io import BytesIO
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from PIL import Image

from maehai.catalog.models import Category, Product, ProductImage

pytestmark = pytest.mark.django_db


def make_source(tmp_path, products, files):
    src = tmp_path / "site"
    (src / "images").mkdir(parents=True)
    for fname in files:
        buf = BytesIO()
        Image.new("RGB", (30, 30), "brown").save(buf, "WEBP")
        (src / "images" / fname).write_bytes(buf.getvalue())
    (src / "manifest.py").write_text(
        f"PRODUCTS = {products!r}\nEXTRA_CATEGORIES = [('other', 'อาหารอื่นๆ')]\n", encoding="utf-8")
    return src


def run(src, *extra):
    call_command("import_site_catalog", "--source", str(src), *extra, stdout=_Null(), stderr=_Null())


class _Null:
    def write(self, *a, **k):
        pass


SAMPLE = [
    ("หมูยอแผ่น (ทดสอบ)", "test-sheet", "moo-yo", "", [], ["one.webp", "two.webp"]),
    ("ก้อยข้าวปุ้น", "test-koi", "other", "", [], ["koi.webp"]),
]


def test_new_products_are_hidden_with_placeholder_prices_and_photos_in_order(tmp_path, seeded):
    src = make_source(tmp_path, SAMPLE, ["one.webp", "two.webp", "koi.webp"])
    run(src)
    p = Product.objects.get(slug="test-sheet")
    assert p.is_active is False and p.category.slug == "moo-yo"
    assert [v.price_satang for v in p.variants.all()] == [10000]
    assert [im.sort_order for im in p.images.order_by("sort_order")] == [0, 1]
    assert Category.objects.get(slug="other").name == "อาหารอื่นๆ"


def test_running_again_adds_nothing_twice(tmp_path, seeded):
    src = make_source(tmp_path, SAMPLE, ["one.webp", "two.webp", "koi.webp"])
    run(src); run(src)
    assert ProductImage.objects.filter(product__slug="test-sheet").count() == 2
    assert Product.objects.filter(slug="test-sheet").count() == 1


def test_existing_product_keeps_owner_prices_and_gets_only_missing_photos(tmp_path, seeded):
    from maehai.catalog.models import ProductVariant

    v = ProductVariant.objects.get(sku="moo-yo-black-pepper-2")
    v.price_satang = 9900
    v.save()
    site = [("หมูยอพริกไทยดำ (ยางเหลือง)", "moo-yo-black-pepper", "moo-yo", "ยางเหลือง", ["yellow"], ["one.webp"])]
    src = make_source(tmp_path, site, ["one.webp"])
    run(src)
    v.refresh_from_db()
    assert v.price_satang == 9900                                       # owner's price untouched
    assert Product.objects.get(slug="moo-yo-black-pepper").images.count() == 1
    run(src)
    assert Product.objects.get(slug="moo-yo-black-pepper").images.count() == 1


def test_activate_flag_shows_new_products(tmp_path, seeded):
    src = make_source(tmp_path, SAMPLE, ["one.webp", "two.webp", "koi.webp"])
    run(src, "--activate")
    assert Product.objects.get(slug="test-koi").is_active is True


def test_missing_photo_is_reported_not_fatal(tmp_path, seeded):
    src = make_source(tmp_path, SAMPLE, ["koi.webp"])                  # one.webp and two.webp absent
    run(src)
    assert ProductImage.objects.filter(product__slug="test-sheet").count() == 0
    assert ProductImage.objects.filter(product__slug="test-koi").count() == 1


def test_missing_manifest_is_an_error(tmp_path, seeded):
    with pytest.raises(CommandError):
        call_command("import_site_catalog", "--source", str(tmp_path / "nowhere"), stdout=_Null(), stderr=_Null())


def test_real_manifest_is_consistent(seeded):
    """Every product in the site manifest has a category we know about and a photo file on disk (when downloaded)."""
    import importlib.util

    path = Path(__file__).resolve().parent.parent / "data" / "site_import" / "manifest.py"
    spec = importlib.util.spec_from_file_location("m", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    known = set(Category.objects.values_list("slug", flat=True)) | {s for s, _ in m.EXTRA_CATEGORIES}
    slugs = [p[1] for p in m.PRODUCTS]
    assert len(slugs) == len(set(slugs)) == 28
    assert all(p[2] in known for p in m.PRODUCTS)
