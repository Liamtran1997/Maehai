"""Back office for campaigns. Drafts: campaigns.edit. Publishing, changing a live campaign, ending it: campaigns.publish."""
import uuid

from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from ninja import File, Router
from ninja.errors import HttpError
from ninja.files import UploadedFile
from PIL import Image, UnidentifiedImageError

from maehai.catalog.models import Product
from maehai.core.auth import requires
from maehai.core.models import audit
from maehai.core.permissions import check

from . import services
from .models import Campaign, CampaignProduct
from .schemas import CampaignIn, CampaignListOut, CampaignOut, PreviewTokenOut
from .signing import make_preview_token

router = Router(tags=["admin-campaigns"])

ANIMATED_FORMATS = {"GIF": "animation", "WEBP": "animation"}
STILL_FORMATS = {"JPEG": "image", "PNG": "image", "WEBP": "image"}
IMAGE_EXT = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp", "GIF": ".gif"}
THEMES = {c for c, _ in Campaign.Theme.choices}
HERO_KINDS = {c for c, _ in Campaign.HeroKind.choices}


def _url(request, f) -> str | None:
    return request.build_absolute_uri(f.url) if f else None


def _out(request, c: Campaign) -> dict:
    st = services.status(c)
    return {
        "id": c.pk, "name": c.name, "theme": c.theme, "accent_color": c.accent_color, "decorations": c.decorations,
        "starts_at": c.starts_at, "ends_at": c.ends_at, "published_at": c.published_at, "ended_at": c.ended_at,
        "status": st, "status_label": services.STATUS_LABEL[st],
        "hero_kind": c.hero_kind, "hero_image_url": _url(request, c.hero_image), "hero_poster_url": _url(request, c.hero_poster),
        "hero_video_url": _url(request, c.hero_video), "hero_video_mobile_url": _url(request, c.hero_video_mobile),
        "hero_title": c.hero_title, "hero_subtitle": c.hero_subtitle, "hero_cta_label": c.hero_cta_label, "hero_cta_url": c.hero_cta_url,
        "bar_enabled": c.bar_enabled, "bar_text": c.bar_text, "bar_url": c.bar_url, "collection_title": c.collection_title,
        "products": [{"id": cp.product.pk, "name": cp.product.name} for cp in c.products.select_related("product")],
        "created_by": c.created_by, "updated_by": c.updated_by,
    }


def _get(pk: int) -> Campaign:
    return get_object_or_404(Campaign, pk=pk)


def _guard_edit(request, c: Campaign) -> None:
    """A draft can be edited by anyone who may edit campaigns. Changing a published one needs the publish permission."""
    if services.status(c) != services.DRAFT:
        check(request, "campaigns.publish")


def _apply(c: Campaign, data: CampaignIn, request) -> None:
    if data.theme not in THEMES:
        raise HttpError(422, "ไม่รู้จักธีมนี้")
    if data.hero_kind not in HERO_KINDS:
        raise HttpError(422, "ไม่รู้จักชนิดของส่วนหัว")
    services.check_accent(data.accent_color)
    services.check_window(data.starts_at, data.ends_at, exclude_id=c.pk if c.published_at else None,
                          publishing=bool(c.published_at))
    for field in ("name", "theme", "accent_color", "decorations", "starts_at", "ends_at", "hero_kind", "hero_title",
                  "hero_subtitle", "hero_cta_label", "hero_cta_url", "bar_enabled", "bar_text", "bar_url", "collection_title"):
        setattr(c, field, getattr(data, field))
    if c.hero_kind == Campaign.HeroKind.NONE:
        c.hero_image = c.hero_poster = c.hero_video = c.hero_video_mobile = None
    c.updated_by = request.user.get_username()
    if not c.pk:
        c.created_by = c.updated_by
    c.save()
    ids = list(dict.fromkeys(data.product_ids))
    found = set(Product.objects.filter(pk__in=ids).values_list("pk", flat=True))
    if found != set(ids):
        raise HttpError(422, "มีสินค้าที่ไม่พบในระบบ")
    c.products.all().delete()
    CampaignProduct.objects.bulk_create([CampaignProduct(campaign=c, product_id=pid, sort_order=i) for i, pid in enumerate(ids)])


@router.get("/campaigns", response=CampaignListOut, auth=requires("campaigns.edit"))
def list_campaigns(request):
    qs = Campaign.objects.prefetch_related("products__product")
    return {"items": [_out(request, c) for c in qs]}


@router.post("/campaigns", response=CampaignOut, auth=requires("campaigns.edit"))
def create_campaign(request, data: CampaignIn):
    c = Campaign()
    with transaction.atomic():
        _apply(c, data, request)
    audit(request, "campaign.create", str(c.pk), c.name)
    return _out(request, c)


@router.get("/campaigns/{campaign_id}", response=CampaignOut, auth=requires("campaigns.edit"))
def get_campaign(request, campaign_id: int):
    return _out(request, _get(campaign_id))


@router.put("/campaigns/{campaign_id}", response=CampaignOut, auth=requires("campaigns.edit"))
def update_campaign(request, campaign_id: int, data: CampaignIn):
    c = _get(campaign_id)
    _guard_edit(request, c)
    with transaction.atomic():
        _apply(c, data, request)
    audit(request, "campaign.update", str(c.pk), c.name)
    return _out(request, c)


@router.post("/campaigns/{campaign_id}/publish", response=CampaignOut, auth=requires("campaigns.publish"))
def publish_campaign(request, campaign_id: int):
    c = _get(campaign_id)
    if c.published_at is not None:
        raise HttpError(422, "แคมเปญนี้เผยแพร่แล้ว")
    services.check_publishable(c)
    services.check_window(c.starts_at, c.ends_at, exclude_id=c.pk, publishing=True)
    if services.effective_end(c) <= timezone.now():
        raise HttpError(422, "เวลาจบผ่านไปแล้ว ปรับเวลาก่อนเผยแพร่")
    c.published_at = timezone.now()
    c.updated_by = request.user.get_username()
    c.save(update_fields=["published_at", "updated_by", "updated_at"])
    audit(request, "campaign.publish", str(c.pk), c.name)
    return _out(request, c)


@router.post("/campaigns/{campaign_id}/end", response=CampaignOut, auth=requires("campaigns.publish"))
def end_campaign(request, campaign_id: int):
    """Stops a live campaign now. On a scheduled one it cancels the schedule. Its time is kept for the record."""
    c = _get(campaign_id)
    if c.published_at is None:
        raise HttpError(422, "แคมเปญนี้ยังเป็นร่าง")
    if services.status(c) == services.ENDED:
        raise HttpError(422, "แคมเปญนี้จบแล้ว")
    c.ended_at = timezone.now()
    c.updated_by = request.user.get_username()
    c.save(update_fields=["ended_at", "updated_by", "updated_at"])
    audit(request, "campaign.end", str(c.pk), c.name)
    return _out(request, c)


@router.delete("/campaigns/{campaign_id}", response={204: None}, auth=requires("campaigns.edit"))
def delete_campaign(request, campaign_id: int):
    """Only drafts can be deleted. Anything that was shown to customers stays on record."""
    c = _get(campaign_id)
    if c.published_at is not None:
        raise HttpError(422, "ลบได้เฉพาะแคมเปญที่ยังเป็นร่าง")
    name = c.name
    c.delete()
    audit(request, "campaign.delete", str(campaign_id), name)
    return 204, None


@router.post("/campaigns/{campaign_id}/hero", response=CampaignOut, auth=requires("campaigns.edit"))
def upload_hero(request, campaign_id: int, image: File[UploadedFile]):
    """A still image (JPG, PNG, WebP) or an animation (GIF, animated WebP). An animation gets a still poster made from its first frame."""
    c = _get(campaign_id)
    _guard_edit(request, c)
    if image.size > 8 * 1024 * 1024:
        raise HttpError(422, "ไฟล์ใหญ่เกิน 8 MB")
    try:
        with Image.open(image) as im:
            fmt = im.format
            animated = bool(getattr(im, "is_animated", False))
            im.verify()
    except (UnidentifiedImageError, OSError):
        raise HttpError(422, "ไฟล์นี้ไม่ใช่รูปภาพ") from None
    image.seek(0)
    if fmt not in IMAGE_EXT:
        raise HttpError(422, "รองรับ JPG, PNG, WebP หรือ GIF")
    if fmt == "GIF" or (fmt == "WEBP" and animated):
        kind = Campaign.HeroKind.ANIMATION
        poster = services.poster_from_first_frame(image)
        c.hero_poster.save(f"{c.pk}-poster.jpg", poster, save=False)
    else:
        kind = Campaign.HeroKind.IMAGE
        c.hero_poster.delete(save=False)
    c.hero_image.save(f"{uuid.uuid4().hex}{IMAGE_EXT[fmt]}", image, save=False)
    c.hero_kind = kind
    c.updated_by = request.user.get_username()
    c.save()
    audit(request, "campaign.hero", str(c.pk), kind)
    return _out(request, c)


@router.post("/campaigns/{campaign_id}/hero-video", response=CampaignOut, auth=requires("campaigns.edit"))
def upload_hero_video(request, campaign_id: int, video: File[UploadedFile]):
    """The hero video (MP4 or WebM). The poster is uploaded separately: it is what shows before the video loads."""
    c = _get(campaign_id)
    _guard_edit(request, c)
    ext = services.check_video(video, settings.VIDEO_MAX_BYTES)
    c.hero_video.save(f"{uuid.uuid4().hex}{ext}", video, save=False)
    c.hero_kind = Campaign.HeroKind.VIDEO
    c.updated_by = request.user.get_username()
    c.save()
    audit(request, "campaign.hero_video", str(c.pk), c.hero_video.name)
    return _out(request, c)


@router.post("/campaigns/{campaign_id}/hero-video-mobile", response=CampaignOut, auth=requires("campaigns.edit"))
def upload_hero_video_mobile(request, campaign_id: int, video: File[UploadedFile]):
    """A vertical version for phones. Optional: without it, phones play the main video."""
    c = _get(campaign_id)
    _guard_edit(request, c)
    ext = services.check_video(video, settings.VIDEO_MAX_BYTES)
    c.hero_video_mobile.save(f"{uuid.uuid4().hex}-mobile{ext}", video, save=False)
    c.updated_by = request.user.get_username()
    c.save()
    audit(request, "campaign.hero_video_mobile", str(c.pk), c.hero_video_mobile.name)
    return _out(request, c)


@router.post("/campaigns/{campaign_id}/hero-poster", response=CampaignOut, auth=requires("campaigns.edit"))
def upload_hero_poster(request, campaign_id: int, image: File[UploadedFile]):
    """A still picture (JPG, PNG or WebP) shown before a video loads, on slow connections, or when motion is reduced."""
    c = _get(campaign_id)
    _guard_edit(request, c)
    if image.size > settings.IMAGE_MAX_BYTES:
        raise HttpError(422, f"รูปใหญ่เกิน {settings.IMAGE_MAX_MB} MB")
    try:
        with Image.open(image) as im:
            fmt = im.format
            im.verify()
    except (UnidentifiedImageError, OSError):
        raise HttpError(422, "ไฟล์นี้ไม่ใช่รูปภาพ") from None
    image.seek(0)
    if fmt not in STILL_FORMATS:
        raise HttpError(422, "ภาพปกต้องเป็น JPG, PNG หรือ WebP")
    c.hero_poster.save(f"{uuid.uuid4().hex}-poster{IMAGE_EXT[fmt]}", image, save=False)
    c.updated_by = request.user.get_username()
    c.save()
    audit(request, "campaign.hero_poster", str(c.pk), c.hero_poster.name)
    return _out(request, c)


@router.post("/campaigns/{campaign_id}/preview-token", response=PreviewTokenOut, auth=requires("campaigns.edit"))
def preview_token(request, campaign_id: int):
    """A short-lived token the shop accepts to show this campaign before it goes live."""
    _get(campaign_id)
    return {"token": make_preview_token(campaign_id), "expires_in": 30 * 60}
