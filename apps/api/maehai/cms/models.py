"""Seasonal campaigns: a storefront look (theme, hero, notice bar, featured products) that staff schedule ahead.

A campaign changes only the home page and the notice bar. It never changes prices, coupons or checkout.
See docs/specs/campaigns.md.
"""
from django.db import models

from maehai.catalog.models import Product


class Campaign(models.Model):
    class Theme(models.TextChoices):
        DEFAULT = "default", "ปกติ"
        CANDLE_FESTIVAL = "candle_festival", "แห่เทียนพรรษา"
        SONGKRAN = "songkran", "สงกรานต์"
        NEW_YEAR = "new_year", "ปีใหม่"

    class HeroKind(models.TextChoices):
        NONE = "none", "ใช้แบบปกติ"
        IMAGE = "image", "รูปภาพ"
        ANIMATION = "animation", "ภาพเคลื่อนไหว (GIF)"
        VIDEO = "video", "วิดีโอ"

    name = models.CharField("ชื่อแคมเปญ (ลูกค้าไม่เห็น)", max_length=120)
    theme = models.CharField(max_length=32, choices=Theme.choices, default=Theme.DEFAULT)
    accent_color = models.CharField(max_length=7, blank=True, help_text="#RRGGBB; ว่างไว้ = ใช้สีของธีม")
    decorations = models.BooleanField(default=True)

    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    published_at = models.DateTimeField(null=True, blank=True, help_text="ว่าง = ยังเป็นร่าง ลูกค้าไม่เห็น")
    ended_at = models.DateTimeField(null=True, blank=True, help_text="ตั้งเมื่อกดจบก่อนกำหนด")

    hero_kind = models.CharField(max_length=16, choices=HeroKind.choices, default=HeroKind.NONE)
    hero_image = models.ImageField(upload_to="campaigns/%Y/%m/", blank=True)
    hero_poster = models.ImageField(upload_to="campaigns/%Y/%m/", blank=True)
    hero_video = models.FileField(upload_to="campaigns/%Y/%m/", blank=True, help_text="MP4 หรือ WebM ไม่เกิน VIDEO_MAX_MB")
    hero_video_mobile = models.FileField(upload_to="campaigns/%Y/%m/", blank=True, help_text="เวอร์ชันแนวตั้งสำหรับมือถือ (ไม่บังคับ)")
    hero_title = models.CharField(max_length=80, blank=True)
    hero_subtitle = models.CharField(max_length=160, blank=True)
    hero_cta_label = models.CharField(max_length=40, blank=True)
    hero_cta_url = models.CharField(max_length=300, blank=True)

    bar_enabled = models.BooleanField(default=False)
    bar_text = models.CharField(max_length=80, blank=True)
    bar_url = models.CharField(max_length=300, blank=True)

    collection_title = models.CharField(max_length=80, blank=True)

    created_by = models.CharField(max_length=150, blank=True)
    updated_by = models.CharField(max_length=150, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["starts_at", "id"]

    def __str__(self) -> str:
        return self.name


class CampaignProduct(models.Model):
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name="products")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="+")
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]
        constraints = [models.UniqueConstraint(fields=["campaign", "product"], name="uniq_campaign_product")]
