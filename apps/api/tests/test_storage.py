import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from maehai.catalog.models import Product, ProductImage
from maehai.payments.models import Payment
from tests.test_payments import charge, upload
from tests.test_product_management import PEPPER, gallery, img

pytestmark = pytest.mark.django_db
API_DIR = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------- where files land (local backend, the default)
def test_product_photos_are_filed_by_product_then_year_and_month(staff_client, seeded, settings):
    pid = Product.objects.get(slug=PEPPER).id
    staff_client.post(gallery(pid), {"image": img()})
    name = ProductImage.objects.get(product_id=pid).image.name
    assert re.fullmatch(rf"products/{pid}/\d{{4}}/\d{{2}}/[0-9a-f]{{32}}\.png", name), name
    assert (settings.MEDIA_ROOT / name).exists()


def test_payment_slips_are_private_and_never_under_public_media(client, staff_client, seeded, settings):
    order = client.post("/api/orders", _order_body(), content_type="application/json").json()
    charge(client, order)
    pid = upload(client, order).json()["id"]
    name = Payment.objects.get(pk=pid).slip.name
    assert re.fullmatch(r"slips/\d{4}/\d{2}/[0-9a-f]{32}\.png", name), name
    assert (settings.PRIVATE_MEDIA_ROOT / name).exists()
    assert not (settings.MEDIA_ROOT / name).exists()                       # what Caddy serves
    assert staff_client.get(f"/api/admin/payments/{pid}/slip").status_code == 200


def _order_body():
    from maehai.shipping.schedule import earliest_fulfillment_date

    return {"items": [{"sku": "moo-yo-black-pepper-2", "quantity": 1}], "customer_name": "ทดสอบ", "phone": "0812345678",
            "shipping_method": "pickup-srinarong", "requested_date": earliest_fulfillment_date().isoformat()}


def test_size_limit_comes_from_settings(staff_client, seeded, settings):
    pid = Product.objects.get(slug=PEPPER).id
    settings.IMAGE_MAX_BYTES = 10                                           # any real photo is bigger
    r = staff_client.post(gallery(pid), {"image": img()})
    assert r.status_code == 422 and "MB" in r.json()["detail"]
    assert ProductImage.objects.filter(product_id=pid).count() == 0


# ---------------------------------------------------------------- the switch (separate processes: settings load once)
def probe(**env):
    code = ("import django; django.setup()\n"
            "from django.core.files.storage import storages\n"
            "p, v = storages['products'], storages['private']\n"
            "print('|'.join([type(p).__name__, type(v).__name__, getattr(p, 'bucket_name', '-'), str(getattr(v, 'querystring_auth', '-'))]))")
    base = {k: val for k, val in os.environ.items() if not k.startswith(("STORAGE_BACKEND", "AWS_", "DJANGO_", "DATABASE_URL", "REDIS_URL", "PRIVATE_MEDIA_ROOT"))}
    return subprocess.run([sys.executable, "-c", code], cwd=API_DIR, capture_output=True, text=True,
                          env={**base, "DJANGO_SETTINGS_MODULE": "config.settings", "DJANGO_DEBUG": "1", **env})


def test_default_backend_is_local():
    r = probe()
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "FileSystemStorage|PrivateFileSystemStorage|-|-"


def test_s3_backend_keeps_photos_public_and_slips_signed():
    r = probe(STORAGE_BACKEND="s3", AWS_STORAGE_BUCKET_NAME="maehai-shop-test")
    assert r.returncode == 0, r.stderr
    products, private, bucket, private_signed = r.stdout.strip().split("|")
    assert products == "S3Storage" and private == "S3Storage"
    assert bucket == "maehai-shop-test"
    assert private_signed == "True"                                         # slip links expire; products use plain URLs


def test_s3_without_a_bucket_refuses_to_start():
    r = probe(STORAGE_BACKEND="s3")
    assert r.returncode != 0 and "AWS_STORAGE_BUCKET_NAME" in r.stderr


def test_unknown_backend_refuses_to_start():
    r = probe(STORAGE_BACKEND="ftp")
    assert r.returncode != 0 and "STORAGE_BACKEND" in r.stderr
