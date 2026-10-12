import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

pytestmark = pytest.mark.django_db(transaction=True)

BEFORE = [("catalog", "0003_category_is_active_product_is_featured_promotion")]
AFTER = [("catalog", "0004_productimage")]


def migrate_to(targets):
    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate(targets)
    return executor.loader.project_state(targets).apps


def test_existing_single_photos_become_the_first_gallery_image():
    old = migrate_to(BEFORE)
    Category, Product = old.get_model("catalog", "Category"), old.get_model("catalog", "Product")
    cat = Category.objects.create(name="หมูยอ", slug="moo-yo")
    with_photo = Product.objects.create(category=cat, slug="with", name="มีรูป", image="products/old-photo.png")
    without = Product.objects.create(category=cat, slug="without", name="ไม่มีรูป")

    new = migrate_to(AFTER)
    ProductImage = new.get_model("catalog", "ProductImage")
    rows = list(ProductImage.objects.values_list("product_id", "image", "sort_order"))
    assert rows == [(with_photo.id, "products/old-photo.png", 0)]
    assert not ProductImage.objects.filter(product_id=without.id).exists()
    migrate_to(AFTER)   # already at the latest state: nothing to do, nothing duplicated
    assert ProductImage.objects.count() == 1
