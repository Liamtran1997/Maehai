"""Load the products from the old website's manifest (see apps/api/data/site_import/manifest.py).

Safe to run again: existing products are matched by slug and keep their prices, descriptions and stock settings.
Photos are added only to products that have none yet.

New products are created HIDDEN with placeholder prices (฿100 per size). The site has no prices, so the owner must
enter the real ones before turning a product on (or pass --activate once they are checked).
"""
import importlib.util
import uuid
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from maehai.catalog.models import Category, Product, ProductImage, ProductVariant

PLACEHOLDER_PRICE = 10000   # satang: ฿100, obviously a placeholder, shown only in the admin
SIZES = ["เล็ก", "กลาง", "ใหญ่"]


def _load_manifest(path: Path):
    if not path.is_file():
        raise CommandError(f"no manifest at {path}")
    spec = importlib.util.spec_from_file_location("site_manifest", path)
    if spec is None or spec.loader is None:
        raise CommandError(f"cannot read {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Command(BaseCommand):
    help = "Import products and photos from the old website's manifest. Hidden placeholder prices for new products."

    def add_arguments(self, parser):
        parser.add_argument("--source", default=str(settings.BASE_DIR / "data" / "site_import"),
                            help="Folder with manifest.py and images/")
        parser.add_argument("--activate", action="store_true", help="Show new products on the shop (only after prices are set)")

    @transaction.atomic
    def handle(self, *args, source, activate, **opts):
        src = Path(source)
        m = _load_manifest(src / "manifest.py")
        images_dir = src / "images"

        for slug, name in getattr(m, "EXTRA_CATEGORIES", []):
            Category.objects.get_or_create(slug=slug, defaults={"name": name, "sort_order": 90})

        created = updated = photos = missing_files = 0
        for site_name, slug, cat_slug, subtitle, bands, files in m.PRODUCTS:
            category = Category.objects.get(slug=cat_slug)
            product, is_new = Product.objects.get_or_create(
                slug=slug,
                defaults={"name": site_name.split(" (")[0].strip(), "category": category,
                          "subtitle": subtitle, "bands": bands, "is_active": activate},
            )
            if is_new:
                created += 1
                sizes = SIZES if slug == "moo-yo-sizes" else ["ปกติ"]
                for i, label in enumerate(sizes, 1):
                    ProductVariant.objects.create(product=product, label=label, sku=f"{slug}-{i}",
                                                  price_satang=PLACEHOLDER_PRICE, sort_order=i - 1)
            else:
                # the site is the source of names and colours; prices and descriptions stay as the owner set them
                changed = False
                for field, value in (("subtitle", subtitle), ("bands", bands)):
                    if value and getattr(product, field) != value:
                        setattr(product, field, value); changed = True
                if changed:
                    product.save(); updated += 1

            if not product.images.exists():
                for n, fname in enumerate(files):
                    path = images_dir / fname.replace("%", "_")
                    if not path.exists():
                        missing_files += 1
                        self.stderr.write(f"missing photo for {slug}: {path.name}")
                        continue
                    im = ProductImage(product=product, sort_order=n)
                    im.image.save(f"{uuid.uuid4().hex}.webp", ContentFile(path.read_bytes()), save=True)
                    photos += 1

        self.stdout.write(self.style.SUCCESS(
            f"products created: {created} (hidden: {0 if activate else created}), updated: {updated}, photos added: {photos}"
            + (f", missing files: {missing_files}" if missing_files else "")))
        if created and not activate:
            self.stdout.write(self.style.WARNING("New products are HIDDEN with placeholder prices. Enter the real prices in /admin, then turn them on."))
