from django.db import transaction
from ninja.errors import HttpError

from .models import Band, Badge, Category, Product, ProductVariant
from .schemas import ProductIn


def _validate(data: ProductIn) -> Category:
    valid_bands = set(Band.values)
    if not set(data.bands) <= valid_bands:
        raise HttpError(422, f"bands must be in {sorted(valid_bands)}")
    if data.badge not in Badge.values:
        raise HttpError(422, f"badge must be in {Badge.values}")
    skus = [v.sku for v in data.variants]
    labels = [v.label for v in data.variants]
    if len(set(skus)) != len(skus) or len(set(labels)) != len(labels):
        raise HttpError(422, "variant sku and label must be unique within a product")
    try:
        return Category.objects.get(slug=data.category_slug)
    except Category.DoesNotExist:
        raise HttpError(422, "unknown category_slug") from None


@transaction.atomic
def save_product(data: ProductIn, product: Product | None = None) -> Product:
    category = _validate(data)
    fields = data.model_dump(exclude={"category_slug", "variants"})
    if product is None:
        if Product.objects.filter(slug=data.slug).exists():
            raise HttpError(409, "slug already exists")
        product = Product.objects.create(category=category, **fields)
    else:
        if Product.objects.filter(slug=data.slug).exclude(pk=product.pk).exists():
            raise HttpError(409, "slug already exists")
        for k, v in fields.items():
            setattr(product, k, v)
        product.category = category
        product.save()

    # Replace variants by sku: update existing, create new, deactivate removed ones (keeps order history intact).
    existing = {v.sku: v for v in product.variants.all()}
    for i, v in enumerate(data.variants):
        values = {"label": v.label, "price_satang": v.price_satang, "weight_grams": v.weight_grams,
                  "is_active": v.is_active, "sort_order": i}
        if v.sku in existing:
            for k, val in values.items():
                setattr(existing[v.sku], k, val)
            existing[v.sku].save()
        else:
            ProductVariant.objects.create(product=product, sku=v.sku, **values)
    incoming = {v.sku for v in data.variants}
    product.variants.exclude(sku__in=incoming).update(is_active=False)
    return product
