import json
from datetime import timedelta
from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from PIL import Image

from maehai.catalog.models import Category, Product, ProductImage, ProductVariant, Promotion
from maehai.inventory.models import RestockRequest
from maehai.notifications.models import Outbox
from maehai.orders.models import Order

pytestmark = pytest.mark.django_db
JSON = "application/json"
PEPPER = "moo-yo-black-pepper"          # sizes เล็ก 60.00 / กลาง 85.00 / ใหญ่ 150.00
NAEM = "naem-pork"                      # 60.00


def now():
    return timezone.now()


def promo(staff, **over):
    body = {"name": "ลดรับสงกรานต์", "kind": "percent", "value": 10, "scope": "products",
            "product_ids": [Product.objects.get(slug=PEPPER).id], "starts_at": (now() - timedelta(hours=1)).isoformat()}
    body.update(over)
    return staff.post("/api/admin/catalog/promotions", body, content_type=JSON)


def detail(client, slug=PEPPER):
    return client.get(f"/api/catalog/products/{slug}").json()


def variant(d, label):
    return next(v for v in d["variants"] if v["label"] == label)


# ================================================================ promotions
def test_percent_promotion_shows_sale_price_everywhere(client, staff_client, seeded):
    assert promo(staff_client).status_code == 201
    d = detail(client)
    mid = variant(d, "กลาง")
    assert (mid["price_satang"], mid["original_price_satang"], mid["promotion_label"]) == (7650, 8500, "ลด 10%")
    assert d["promotion"]["name"] == "ลดรับสงกรานต์"
    card = next(p for p in client.get("/api/catalog/products").json() if p["slug"] == PEPPER)
    assert (card["price_from_satang"], card["original_price_from_satang"], card["promotion_label"]) == (5400, 6000, "ลด 10%")
    other = next(p for p in client.get("/api/catalog/products").json() if p["slug"] == NAEM)
    assert other["original_price_from_satang"] is None and other["promotion_label"] is None


def test_order_is_charged_the_sale_price_and_remembers_it(client, staff_client, place):
    promo(staff_client)
    o = place(items=[{"sku": f"{PEPPER}-2", "quantity": 2}, {"sku": "naem-pork-1", "quantity": 1}]).json()
    item = next(i for i in o["items"] if i["sku"] == f"{PEPPER}-2")
    assert (item["unit_price_satang"], item["list_price_satang"], item["promotion_name"]) == (7650, 8500, "ลดรับสงกรานต์")
    assert o["subtotal_satang"] == 7650 * 2 + 6000 and o["discount_satang"] == 850 * 2
    # ending the promotion later never changes an order already placed
    Promotion.objects.update(ends_at=now())
    assert client.get(f"/api/orders/{o['number']}", {"token": o["token"]}).json()["subtotal_satang"] == 7650 * 2 + 6000


def test_category_and_shop_wide_promotions(client, staff_client, seeded):
    naem_cat = Product.objects.get(slug=NAEM).category_id
    promo(staff_client, kind="amount", value=1000, scope="categories", product_ids=[], category_ids=[naem_cat])
    assert variant(detail(client, NAEM), "ปกติ")["price_satang"] == 5000
    assert variant(detail(client), "กลาง")["original_price_satang"] is None      # other category untouched
    promo(staff_client, name="ทั้งร้าน", value=5, scope="all", product_ids=[])
    assert variant(detail(client), "กลาง")["price_satang"] == 8075


def test_overlapping_promotions_do_not_stack_best_one_wins(client, staff_client, seeded):
    promo(staff_client, name="ลด 10", value=10)
    promo(staff_client, name="ลด 20 บาท", kind="amount", value=2000)
    promo(staff_client, name="ทั้งร้าน 5%", value=5, scope="all", product_ids=[])
    mid = variant(detail(client), "กลาง")       # 85.00: 10% = 8.50, 20 baht = 20.00, 5% = 4.25
    assert mid["price_satang"] == 6500 and mid["promotion_label"] == "ลด ฿20"
    big = variant(detail(client), "ใหญ่")       # 150.00: 10% = 15.00 < 20.00
    assert big["price_satang"] == 13000


@pytest.mark.parametrize("window, applies", [
    ({"starts_at": timedelta(hours=1)}, False),                                  # not started
    ({"starts_at": -timedelta(days=2), "ends_at": -timedelta(hours=1)}, False),  # ended
    ({"starts_at": -timedelta(hours=1), "ends_at": timedelta(hours=1)}, True),
    ({"starts_at": -timedelta(hours=1), "is_active": False}, False),             # switched off
])
def test_promotion_window(client, staff_client, seeded, window, applies):
    over = {k: (now() + v).isoformat() if isinstance(v, timedelta) else v for k, v in window.items()}
    assert promo(staff_client, **over).status_code == 201
    assert (variant(detail(client), "กลาง")["original_price_satang"] is not None) is applies


def test_amount_bigger_than_price_is_ignored_and_warned(client, staff_client, seeded):
    r = promo(staff_client, kind="amount", value=7000)          # >= เล็ก 60.00, < กลาง 85.00
    assert any("เล็ก" in w for w in r.json()["warnings"])
    d = detail(client)
    assert variant(d, "เล็ก")["original_price_satang"] is None
    assert variant(d, "กลาง")["price_satang"] == 1500


def test_percent_rounds_half_up():
    p = Promotion(kind="percent", value=10)
    assert p.discount_for(105) == 11 and p.discount_for(104) == 10


@pytest.mark.parametrize("over", [
    {"value": 0}, {"value": 91}, {"kind": "bogus"}, {"scope": "bogus"},
    {"product_ids": []}, {"scope": "categories", "category_ids": []},
    {"ends_at": "2020-01-01T00:00:00+07:00"},
])
def test_promotion_validation(staff_client, seeded, over):
    assert promo(staff_client, **over).status_code == 422


def test_end_and_delete_rules(client, staff_client, seeded):
    running = promo(staff_client).json()
    assert staff_client.delete(f"/api/admin/catalog/promotions/{running['id']}").status_code == 409   # keep history
    ended = staff_client.post(f"/api/admin/catalog/promotions/{running['id']}/end").json()
    assert ended["state"] == "ended" and variant(detail(client), "กลาง")["original_price_satang"] is None
    later = promo(staff_client, starts_at=(now() + timedelta(days=3)).isoformat()).json()
    assert later["state"] == "scheduled"
    assert staff_client.delete(f"/api/admin/catalog/promotions/{later['id']}").status_code == 204


def test_admin_edits_list_price_not_the_sale_price(client, staff_client, seeded):
    promo(staff_client)
    p = next(x for x in staff_client.get("/api/admin/catalog/products").json() if x["slug"] == PEPPER)
    assert variant(p, "กลาง")["price_satang"] == 8500        # list price, not 76.50
    body = {"category_slug": p["category"]["slug"], "slug": p["slug"], "name": p["name"], "name_en": "Black pepper moo yo",
            "variants": [{"label": v["label"], "sku": v["sku"], "price_satang": v["price_satang"]} for v in p["variants"]]}
    staff_client.put(f"/api/admin/catalog/products/{p['id']}", body, content_type=JSON)
    assert ProductVariant.objects.get(sku=f"{PEPPER}-2").price_satang == 8500    # discount never baked into the catalog
    assert Product.objects.get(slug=PEPPER).name_en == "Black pepper moo yo"   # and name_en now survives edits


def test_promotions_require_staff(client, seeded):
    assert client.get("/api/admin/catalog/promotions").status_code == 401


# ================================================================ categories
def cat(staff, **over):
    return staff.post("/api/admin/catalog/categories", {"name": "ของฝาก", "slug": "gifts", **over}, content_type=JSON)


def test_category_crud(staff_client, seeded):
    c = cat(staff_client).json()
    assert c["product_count"] == 0 and c["is_active"]
    assert cat(staff_client).status_code == 409                                    # duplicate slug
    r = staff_client.put(f"/api/admin/catalog/categories/{c['id']}", {"name": "ของฝากอุบล", "slug": "gifts", "sort_order": 3}, content_type=JSON)
    assert r.json()["name"] == "ของฝากอุบล"
    assert staff_client.delete(f"/api/admin/catalog/categories/{c['id']}").status_code == 204


def test_category_with_products_cannot_be_deleted(staff_client, seeded):
    used = Category.objects.get(slug="naem")
    r = staff_client.delete(f"/api/admin/catalog/categories/{used.id}")
    assert r.status_code == 409 and "ซ่อน" in r.json()["detail"]


def test_hidden_category_hides_its_products_and_blocks_orders(client, staff_client, place):
    naem = Category.objects.get(slug="naem")
    staff_client.put(f"/api/admin/catalog/categories/{naem.id}", {"name": naem.name, "slug": "naem", "is_active": False}, content_type=JSON)
    assert "naem" not in [c["slug"] for c in client.get("/api/catalog/categories").json()]
    assert NAEM not in [p["slug"] for p in client.get("/api/catalog/products").json()]
    assert client.get(f"/api/catalog/products/{NAEM}").status_code == 404
    assert place(items=[{"sku": "naem-pork-1", "quantity": 1}]).status_code == 422
    assert "naem" in [c["slug"] for c in staff_client.get("/api/admin/catalog/categories").json()]   # staff still see it


# ================================================================ images, featured, ordering
def img(fmt="PNG", name="p.png", ctype="image/png"):
    b = BytesIO()
    Image.new("RGB", (40, 40), "red").save(b, fmt)
    return SimpleUploadedFile(name, b.getvalue(), content_type=ctype)


def gallery(pid):
    return f"/api/admin/catalog/products/{pid}/images"


def test_gallery_add_reorder_and_delete(client, staff_client, seeded, settings):
    pid = Product.objects.get(slug=PEPPER).id
    assert staff_client.post(gallery(pid), {"image": img()}).status_code == 200
    r = staff_client.post(gallery(pid), {"image": img("JPEG", "x.jpg", "image/jpeg")})
    imgs = r.json()["images"]
    assert [i["url"][-4:] for i in imgs] == [".png", ".jpg"]                       # random names, real formats kept
    first_url = detail(client)["image_url"]
    assert first_url == imgs[0]["url"] and [i["url"] for i in detail(client)["images"]] == [i["url"] for i in imgs]

    # reorder: the second photo becomes the main one everywhere
    a, b = imgs[0]["id"], imgs[1]["id"]
    r = staff_client.put(f"/api/admin/catalog/products/{pid}/image-order", {"ids": [b, a]}, content_type=JSON)
    assert r.status_code == 200 and [i["id"] for i in r.json()["images"]] == [b, a]
    assert detail(client)["image_url"] == imgs[1]["url"]

    # delete the main photo: the file is removed from disk and the other becomes main
    path = settings.MEDIA_ROOT / ProductImage.objects.get(pk=b).image.name
    assert path.exists()
    r = staff_client.delete(f"{gallery(pid)}/{b}")
    assert r.status_code == 200 and [i["id"] for i in r.json()["images"]] == [a]
    assert not path.exists()
    assert detail(client)["image_url"] == imgs[0]["url"]


def test_gallery_is_capped_at_ten(staff_client, seeded):
    pid = Product.objects.get(slug=PEPPER).id
    for _ in range(10):
        assert staff_client.post(gallery(pid), {"image": img()}).status_code == 200
    r = staff_client.post(gallery(pid), {"image": img()})
    assert r.status_code == 422 and "10 รูป" in r.json()["detail"]


def test_reorder_must_list_every_photo_exactly_once(staff_client, seeded):
    pid = Product.objects.get(slug=PEPPER).id
    ids = [staff_client.post(gallery(pid), {"image": img()}).json()["images"][-1]["id"] for _ in range(2)]
    put = lambda body: staff_client.put(f"/api/admin/catalog/products/{pid}/image-order", body, content_type=JSON)
    assert put({"ids": ids[:1]}).status_code == 422                # missing one
    assert put({"ids": [ids[0], ids[0]]}).status_code == 422       # duplicate
    other = Product.objects.get(slug=NAEM).id
    foreign = staff_client.post(gallery(other), {"image": img()}).json()["images"][0]["id"]
    assert put({"ids": [ids[0], foreign]}).status_code == 422      # another product's photo


def test_deleting_a_photo_of_another_product_is_404(staff_client, seeded):
    pid, other = Product.objects.get(slug=PEPPER).id, Product.objects.get(slug=NAEM).id
    foreign = staff_client.post(gallery(other), {"image": img()}).json()["images"][0]["id"]
    assert staff_client.delete(f"{gallery(pid)}/{foreign}").status_code == 404


@pytest.mark.parametrize("make", [
    lambda: SimpleUploadedFile("fake.png", b"not really an image", content_type="image/png"),
    lambda: SimpleUploadedFile("huge.png", b"0" * (5 * 1024 * 1024 + 1), content_type="image/png"),
    lambda: img("GIF", "a.gif", "image/gif"),
])
def test_bad_images_are_refused(staff_client, seeded, make):
    pid = Product.objects.get(slug=PEPPER).id
    assert staff_client.post(gallery(pid), {"image": make()}).status_code == 422
    assert Product.objects.get(pk=pid).images.count() == 0


def test_featured_filter_and_sort_order(client, staff_client, seeded):
    Product.objects.filter(slug__in=[NAEM, "pork-rind"]).update(is_featured=True)
    Product.objects.filter(slug="pork-rind").update(sort_order=0)
    Product.objects.filter(slug=NAEM).update(sort_order=1)
    assert [p["slug"] for p in client.get("/api/catalog/products", {"featured": "true"}).json()] == ["pork-rind", NAEM]


# ================================================================ back in stock
@pytest.fixture
def line(settings):
    from tests.test_notifications import FakeLine, SECRET

    FakeLine.pushed, FakeLine.replies, FakeLine.fail_with = [], [], None
    settings.LINE_CLIENT = "tests.test_notifications.FakeLine"
    settings.LINE_CHANNEL_ACCESS_TOKEN, settings.LINE_CHANNEL_SECRET = "token", SECRET
    return FakeLine


@pytest.fixture
def sold_out(seeded, staff_client):
    ProductVariant.objects.filter(sku=f"{PEPPER}-2").update(track_stock=True)   # tracked, no stock entered = 0
    return f"{PEPPER}-2"


def say(client, text, user="Ucust"):
    from tests.test_notifications import sign

    body = json.dumps({"events": [{"type": "message", "replyToken": "rt", "source": {"userId": user},
                                   "message": {"type": "text", "text": text}}]}).encode()
    return client.post("/api/line/webhook", body, content_type=JSON, HTTP_X_LINE_SIGNATURE=sign(body))


def receive(staff, sku, qty, branch="srinarong"):
    return staff.post("/api/admin/inventory/adjust", {"branch": branch, "sku": sku, "reason": "receive", "quantity": qty}, content_type=JSON)


def test_sold_out_variant_offers_a_line_alert_link(client, line, sold_out):
    v = variant(detail(client), "กลาง")
    assert v["available"] == 0 and v["restock_alert_url"].startswith("https://line.me/R/oaMessage/@maehai/?")
    assert variant(detail(client), "เล็ก")["restock_alert_url"] is None          # not sold out


def test_no_alert_link_when_line_is_not_set_up(client, sold_out, settings):
    settings.LINE_CHANNEL_ACCESS_TOKEN = ""
    assert variant(detail(client), "กลาง")["restock_alert_url"] is None


def test_customer_is_told_once_when_stock_returns(client, staff_client, line, sold_out):
    from urllib.parse import unquote

    text = unquote(variant(detail(client), "กลาง")["restock_alert_url"].split("/?", 1)[1])
    say(client, text); say(client, text)                                         # asking twice = one request
    assert RestockRequest.objects.count() == 1 and "จะแจ้ง" in line.replies[0][1]
    receive(staff_client, sold_out, 5)
    msg = Outbox.objects.get(kind="restocked")
    assert msg.recipient == "Ucust" and "กลับมามีของแล้ว" in msg.text and f"/products/{PEPPER}" in msg.text
    receive(staff_client, sold_out, 5)                                           # more stock later: no second message
    assert Outbox.objects.filter(kind="restocked").count() == 1


def test_asking_for_an_item_in_stock_just_says_so(client, line, seeded):
    say(client, f"แจ้งเตือนสินค้า {PEPPER}-2")                                   # untracked = always available
    assert RestockRequest.objects.count() == 0 and "มีของอยู่แล้ว" in line.replies[0][1]


def test_cancelled_order_returning_the_last_units_alerts_waiters(client, staff_client, line, sold_out, place):
    receive(staff_client, sold_out, 1)
    n = place(items=[{"sku": sold_out, "quantity": 1}]).json()["number"]        # takes the only unit
    say(client, f"แจ้งเตือนสินค้า {sold_out}")
    staff_client.post(f"/api/admin/orders/{n}/status", {"status": "cancelled"}, content_type=JSON)
    assert Outbox.objects.filter(kind="restocked", recipient="Ucust").count() == 1


def test_moving_an_order_between_branches_sends_no_false_alert(client, staff_client, line, sold_out, place):
    receive(staff_client, sold_out, 1, "srinarong"); receive(staff_client, sold_out, 1, "changsanit")
    n1 = place(items=[{"sku": sold_out, "quantity": 1}], shipping_method="cargo-ubon").json()["number"]
    place(items=[{"sku": sold_out, "quantity": 1}], shipping_method="cargo-ubon")  # now 0 everywhere
    say(client, f"แจ้งเตือนสินค้า {sold_out}")
    Outbox.objects.filter(kind="restocked").delete()
    o = Order.objects.get(number=n1)
    other = "changsanit" if o.fulfillment_branch.code == "srinarong" else "srinarong"
    receive(staff_client, sold_out, 1, other)                                     # space at the other branch
    Outbox.objects.filter(kind="restocked").delete(); RestockRequest.objects.update(notified_at=None)
    staff_client.post(f"/api/admin/orders/{n1}/branch", {"branch": other}, content_type=JSON)
    assert Outbox.objects.filter(kind="restocked").exists() is False


def test_admin_category_list_keeps_sort_order(staff_client, seeded):
    for i, c in enumerate(Category.objects.order_by("id")):
        Category.objects.filter(pk=c.pk).update(sort_order=100 - i)   # reverse of insertion order
    got = [c["slug"] for c in staff_client.get("/api/admin/catalog/categories").json()]
    assert got == list(Category.objects.order_by("sort_order", "name").values_list("slug", flat=True))
