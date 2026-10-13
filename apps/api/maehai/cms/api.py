"""What the shop reads: the campaign on right now, or a preview of one that is not live yet."""
from django.http import HttpResponseRedirect
from django.db.models import F
from django.shortcuts import get_object_or_404
from ninja import Router, Schema
from ninja.errors import HttpError

from . import services
from .models import Campaign
from .signing import read_preview_token

router = Router(tags=["shop-campaigns"])


class PublicProductOut(Schema):
    id: int
    name: str
    slug: str


class PublicCampaignOut(Schema):
    id: int
    theme: str
    accent_color: str
    decorations: bool
    hero_kind: str
    hero_image_url: str | None
    hero_poster_url: str | None
    hero_video_url: str | None
    hero_video_mobile_url: str | None
    hero_title: str
    hero_subtitle: str
    hero_cta_label: str
    hero_cta_url: str
    bar_enabled: bool
    bar_text: str
    bar_url: str
    collection_title: str
    products: list[PublicProductOut]
    preview: bool


def _public(request, c: Campaign, preview: bool) -> dict:
    def url(f):
        return request.build_absolute_uri(f.url) if f else None
    return {
        "id": c.pk, "theme": c.theme, "accent_color": c.accent_color, "decorations": c.decorations,
        "hero_kind": c.hero_kind, "hero_image_url": url(c.hero_image), "hero_poster_url": url(c.hero_poster),
        "hero_video_url": url(c.hero_video), "hero_video_mobile_url": url(c.hero_video_mobile),
        "hero_title": c.hero_title, "hero_subtitle": c.hero_subtitle, "hero_cta_label": c.hero_cta_label,
        "hero_cta_url": c.hero_cta_url, "bar_enabled": c.bar_enabled, "bar_text": c.bar_text, "bar_url": c.bar_url,
        "collection_title": c.collection_title,
        "products": [{"id": cp.product.pk, "name": cp.product.name, "slug": cp.product.slug} for cp in c.products.select_related("product")],
        "preview": preview,
    }


@router.get("/campaign/current", response=PublicCampaignOut | None)
def current_campaign(request, preview: str = ""):
    """The campaign to show now. With a valid preview token, that campaign even if it is a draft."""
    if preview:
        pk = read_preview_token(preview)
        if pk is None:
            raise HttpError(404, "ลิงก์ตัวอย่างหมดอายุหรือไม่ถูกต้อง")
        c = Campaign.objects.filter(pk=pk).first()
        if c is None:
            raise HttpError(404, "ไม่พบแคมเปญนี้")
        return _public(request, c, preview=True)
    c = services.current()
    return _public(request, c, preview=False) if c else None


@router.get("/campaign/{campaign_id}/go", response={302: None})
def campaign_go(request, campaign_id: int):
    """The hero button. Counts one press for a campaign that is live now, then sends the customer on.
    No cookies and no personal data: only the count goes up."""
    c = get_object_or_404(Campaign, pk=campaign_id)
    if services.status(c) == services.LIVE:
        Campaign.objects.filter(pk=c.pk).update(hero_clicks=F("hero_clicks") + 1)
    return HttpResponseRedirect(services.safe_redirect(c.hero_cta_url or "/"))
