import django.db.models.deletion
from django.db import migrations, models


def copy_single_photos(apps, schema_editor):
    """Each product's existing single photo becomes its first gallery image."""
    Product = apps.get_model("catalog", "Product")
    ProductImage = apps.get_model("catalog", "ProductImage")
    for p in Product.objects.exclude(image="").exclude(image__isnull=True):
        ProductImage.objects.create(product=p, image=p.image.name, sort_order=0)


class Migration(migrations.Migration):
    dependencies = [("catalog", "0003_category_is_active_product_is_featured_promotion")]

    operations = [
        migrations.CreateModel(
            name="ProductImage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("image", models.ImageField(upload_to="products/")),
                ("sort_order", models.PositiveSmallIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="images", to="catalog.product")),
            ],
            options={"ordering": ["sort_order", "id"]},
        ),
        migrations.RunPython(copy_single_photos, migrations.RunPython.noop),
        migrations.RemoveField(model_name="product", name="image"),
    ]
