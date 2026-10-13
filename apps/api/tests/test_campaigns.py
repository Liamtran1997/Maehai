"""Campaigns: who may do what, the schedule rules, what may be published, and what the shop is shown."""
from datetime import timedelta
from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.utils import timezone
from PIL import Image

from maehai.catalog.models import Product
from maehai.cms import services
from maehai.cms.models import Campaign
from maehai.cms.signing import make_preview_token
from maehai.core.models import AuditLog

pytestmark = pytest.mark.django_db
JSON = "application/json"
NAEM = "naem-pork-1"


def now():
    return timezone.now()


def body(**over):
    base = {
        "name": "แห่เทียนพรรษา 2570", "theme": "candle_festival", "accent_color": "#9A4A10", "decorations": True,
        "starts_at": (now() + timedelta(days=10)).isoformat(), "ends_at": (now() + timedelta(days=18)).isoformat(),
        "hero_kind": "none", "hero_title": "แห่เทียนพรรษา", "hero_subtitle": "", "hero_cta_label": "", "hero_cta_url": "",
        "bar_enabled": False, "bar_text": "", "bar_url": "", "collection_title": "ของฝากเทศกาล", "product_ids": [],
    }
    base.update(over)
    return base


def product_id():
    return Product.objects.get(variants__sku=NAEM).pk


def image_file(fmt="PNG", size=(40, 40), frames=1, name=None):
    buf = BytesIO()
    if frames > 1:
        imgs = [Image.new("RGB", size, (i * 60 % 255, 80, 120)) for i in range(frames)]
        imgs[0].save(buf, format=fmt, save_all=True, append_images=imgs[1:], duration=100, loop=0)
    else:
        Image.new("RGB", size, (200, 40, 40)).save(buf, format=fmt)
    buf.seek(0)
    return SimpleUploadedFile(name or f"hero.{fmt.lower()}", buf.getvalue(), content_type=f"image/{fmt.lower()}")


def create(client, **over):
    r = client.post("/api/admin/campaigns", body(**over), content_type=JSON)
    assert r.status_code == 200, r.content
    return r.json()


# ================================================================ who may do what
def test_owner_manager_and_sales_can_create_and_publish(as_role, staff_client):
    for role in ("owner", "manager", "sales"):
        c = as_role(role) if role != "owner" else staff_client
        created = create(c, name=f"ทดสอบ {role}")
        assert created["status"] == "draft"


def test_content_and_warehouse_cannot_touch_campaigns(as_role):
    for role in ("content", "warehouse", "branch_manager"):
        c = as_role(role)
        assert c.get("/api/admin/campaigns").status_code == 403
        assert c.post("/api/admin/campaigns", body(), content_type=JSON).status_code == 403


def test_sales_can_publish(as_role, staff_client):
    created = create(staff_client)
    r = as_role("sales").post(f"/api/admin/campaigns/{created['id']}/publish")
    assert r.status_code == 200, r.content
    assert r.json()["status"] == "scheduled"


def test_anonymous_cannot_use_admin_campaigns():
    assert Client().get("/api/admin/campaigns").status_code in (401, 403)


# ================================================================ schedule rules
def test_end_must_be_after_start(staff_client):
    r = staff_client.post("/api/admin/campaigns", body(starts_at=(now() + timedelta(days=3)).isoformat(),
                                                      ends_at=(now() + timedelta(days=2)).isoformat()), content_type=JSON)
    assert r.status_code == 422


def test_published_campaigns_cannot_overlap(staff_client):
    a = create(staff_client, name="สงกรานต์")
    staff_client.post(f"/api/admin/campaigns/{a['id']}/publish")
    b = create(staff_client, name="ปีใหม่ ซ้อนกัน", starts_at=(now() + timedelta(days=12)).isoformat(),
               ends_at=(now() + timedelta(days=20)).isoformat())
    r = staff_client.post(f"/api/admin/campaigns/{b['id']}/publish")
    assert r.status_code == 422
    assert "สงกรานต์" in r.json()["detail"]


def test_drafts_may_overlap_each_other(staff_client):
    create(staff_client, name="ร่าง ก")
    create(staff_client, name="ร่าง ข")       # no error: only published campaigns are checked


def test_status_follows_time(staff_client):
    c = Campaign.objects.create(name="x", starts_at=now() - timedelta(days=1), ends_at=now() + timedelta(days=1),
                                published_at=now())
    assert services.status(c) == services.LIVE
    c.starts_at = now() + timedelta(hours=1)
    assert services.status(c) == services.SCHEDULED
    c.ends_at = now() - timedelta(minutes=1)
    assert services.status(c) == services.ENDED


def test_ending_early_stops_the_campaign_now(staff_client):
    c = create(staff_client)
    staff_client.post(f"/api/admin/campaigns/{c['id']}/publish")
    r = staff_client.post(f"/api/admin/campaigns/{c['id']}/end")
    assert r.status_code == 200
    assert r.json()["status"] == "ended"
    assert AuditLog.objects.filter(action="campaign.end").exists()


# ================================================================ publishing rules
def test_animation_needs_its_image_before_publishing(staff_client):
    c = create(staff_client, hero_kind="animation")
    r = staff_client.post(f"/api/admin/campaigns/{c['id']}/publish")
    assert r.status_code == 422
    assert "ยังไม่มีรูปส่วนหัว" in r.json()["detail"]


def test_bar_needs_text_before_publishing(staff_client):
    c = create(staff_client, bar_enabled=True, bar_text="")
    r = staff_client.post(f"/api/admin/campaigns/{c['id']}/publish")
    assert r.status_code == 422


def test_accent_must_read_well_with_white_text(staff_client):
    r = staff_client.post("/api/admin/campaigns", body(accent_color="#FFD700"), content_type=JSON)
    assert r.status_code == 422
    assert "อ่านยาก" in r.json()["detail"]
    r = staff_client.post("/api/admin/campaigns", body(accent_color="blue"), content_type=JSON)
    assert r.status_code == 422


def test_drafts_can_be_deleted_but_published_ones_cannot(staff_client):
    d = create(staff_client)
    assert staff_client.delete(f"/api/admin/campaigns/{d['id']}").status_code == 204
    p = create(staff_client, name="เผยแพร่แล้ว", starts_at=(now() + timedelta(days=40)).isoformat(),
               ends_at=(now() + timedelta(days=45)).isoformat())
    staff_client.post(f"/api/admin/campaigns/{p['id']}/publish")
    assert staff_client.delete(f"/api/admin/campaigns/{p['id']}").status_code == 422


def test_a_published_campaign_needs_publish_permission_to_change(as_role, staff_client):
    p = create(staff_client, starts_at=(now() + timedelta(days=40)).isoformat(),
               ends_at=(now() + timedelta(days=45)).isoformat())
    staff_client.post(f"/api/admin/campaigns/{p['id']}/publish")
    r = as_role("content").put(f"/api/admin/campaigns/{p['id']}", body(name="แก้"), content_type=JSON)
    assert r.status_code == 403


# ================================================================ uploads
def test_gif_becomes_an_animation_with_a_still_poster(staff_client):
    c = create(staff_client)
    r = staff_client.post(f"/api/admin/campaigns/{c['id']}/hero", {"image": image_file("GIF", frames=3, name="hero.gif")})
    assert r.status_code == 200, r.content
    out = r.json()
    assert out["hero_kind"] == "animation"
    assert out["hero_image_url"] and out["hero_poster_url"]


def test_still_image_clears_any_poster(staff_client):
    c = create(staff_client)
    staff_client.post(f"/api/admin/campaigns/{c['id']}/hero", {"image": image_file("GIF", frames=2, name="a.gif")})
    r = staff_client.post(f"/api/admin/campaigns/{c['id']}/hero", {"image": image_file("PNG")})
    assert r.json()["hero_kind"] == "image"
    assert r.json()["hero_poster_url"] is None


def test_upload_refuses_files_that_are_not_images(staff_client):
    c = create(staff_client)
    bad = SimpleUploadedFile("video.mp4", b"not an image at all", content_type="video/mp4")
    r = staff_client.post(f"/api/admin/campaigns/{c['id']}/hero", {"image": bad})
    assert r.status_code == 422


def test_upload_refuses_files_over_the_limit(staff_client):
    c = create(staff_client)
    big = SimpleUploadedFile("big.png", b"0" * (9 * 1024 * 1024), content_type="image/png")
    r = staff_client.post(f"/api/admin/campaigns/{c['id']}/hero", {"image": big})
    assert r.status_code == 422


# ================================================================ what the shop sees
def test_shop_sees_nothing_when_no_campaign_is_live(staff_client):
    assert Client().get("/api/shop/campaign/current").json() is None


def test_shop_sees_the_live_campaign_with_its_products(staff_client, seeded):
    c = create(staff_client, product_ids=[product_id()], bar_enabled=True, bar_text="สั่งก่อน 10 เม.ย.")
    Campaign.objects.filter(pk=c["id"]).update(starts_at=now() - timedelta(hours=1), published_at=now())
    r = Client().get("/api/shop/campaign/current")
    assert r.status_code == 200
    out = r.json()
    assert out["theme"] == "candle_festival"
    assert out["bar_text"] == "สั่งก่อน 10 เม.ย."
    assert out["products"][0]["name"]
    assert out["preview"] is False


def test_shop_does_not_see_a_draft_or_a_scheduled_campaign(staff_client):
    create(staff_client)                       # draft
    s = create(staff_client, name="อีกไม่นาน", starts_at=(now() + timedelta(days=5)).isoformat(),
               ends_at=(now() + timedelta(days=6)).isoformat())
    staff_client.post(f"/api/admin/campaigns/{s['id']}/publish")
    assert Client().get("/api/shop/campaign/current").json() is None


def test_shop_stops_showing_a_campaign_when_it_ends(staff_client):
    c = create(staff_client)
    Campaign.objects.filter(pk=c["id"]).update(starts_at=now() - timedelta(hours=1), published_at=now())
    assert Client().get("/api/shop/campaign/current").json() is not None
    staff_client.post(f"/api/admin/campaigns/{c['id']}/end")
    assert Client().get("/api/shop/campaign/current").json() is None


def test_preview_shows_a_draft_with_a_valid_token(staff_client):
    c = create(staff_client)
    token = staff_client.post(f"/api/admin/campaigns/{c['id']}/preview-token").json()["token"]
    r = Client().get("/api/shop/campaign/current", {"preview": token})
    assert r.status_code == 200
    assert r.json()["preview"] is True


def test_preview_refuses_a_bad_token(staff_client):
    assert Client().get("/api/shop/campaign/current", {"preview": "nonsense"}).status_code == 404


def test_preview_token_expires(staff_client):
    c = create(staff_client)
    token = make_preview_token(c["id"])
    from maehai.cms import signing
    real = signing.MAX_AGE
    signing.MAX_AGE = -1          # every token is already too old
    try:
        assert Client().get("/api/shop/campaign/current", {"preview": token}).status_code == 404
    finally:
        signing.MAX_AGE = real


def test_public_response_hides_internal_names(staff_client):
    c = create(staff_client)
    Campaign.objects.filter(pk=c["id"]).update(starts_at=now() - timedelta(hours=1), published_at=now())
    out = Client().get("/api/shop/campaign/current").json()
    assert "created_by" not in out and "updated_by" not in out
