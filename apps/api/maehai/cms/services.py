"""Rules for campaigns: status by time, no overlaps between published campaigns, what may be published, contrast."""
import io
import re
from datetime import datetime

from django.core.files.base import ContentFile
from django.utils import timezone
from ninja.errors import HttpError
from PIL import Image, UnidentifiedImageError

from .models import Campaign

DRAFT, SCHEDULED, LIVE, ENDED = "draft", "scheduled", "live", "ended"
STATUS_LABEL = {DRAFT: "ร่าง", SCHEDULED: "ตั้งเวลาแล้ว", LIVE: "กำลังแสดง", ENDED: "จบแล้ว"}
HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")
WHITE_TEXT_MIN_CONTRAST = 4.5


def effective_end(c: Campaign) -> datetime:
    """The moment a campaign stops showing: its end time, or earlier if staff ended it by hand."""
    return min(c.ends_at, c.ended_at) if c.ended_at else c.ends_at


def status(c: Campaign, now: datetime | None = None) -> str:
    now = now or timezone.now()
    if c.published_at is None:
        return DRAFT
    if now >= effective_end(c):
        return ENDED
    if now < c.starts_at:
        return SCHEDULED
    return LIVE


def current(now: datetime | None = None) -> Campaign | None:
    """The one campaign the shop shows right now, if any. Published campaigns never overlap, so there is at most one."""
    now = now or timezone.now()
    live = [c for c in Campaign.objects.filter(published_at__isnull=False, starts_at__lte=now)
            if effective_end(c) > now]
    return max(live, key=lambda c: c.starts_at, default=None)


def overlapping(starts_at: datetime, ends_at: datetime, exclude_id: int | None = None) -> list[Campaign]:
    """Published, not-yet-ended campaigns whose time overlaps [starts_at, ends_at)."""
    published = Campaign.objects.filter(published_at__isnull=False, starts_at__lt=ends_at)
    if exclude_id:
        published = published.exclude(pk=exclude_id)
    return [c for c in published if effective_end(c) > starts_at]


def relative_luminance(hex_color: str) -> float:
    def channel(v: int) -> float:
        s = v / 255
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast_with_white(hex_color: str) -> float:
    return 1.05 / (relative_luminance(hex_color) + 0.05)


def check_accent(hex_color: str) -> None:
    if not hex_color:
        return
    if not HEX.match(hex_color):
        raise HttpError(422, "สีต้องอยู่ในรูปแบบ #RRGGBB เช่น #0B5D82")
    if contrast_with_white(hex_color) < WHITE_TEXT_MIN_CONTRAST:
        raise HttpError(422, "สีนี้ทำให้ตัวอักษรขาวอ่านยาก เลือกสีที่เข้มกว่านี้")


def check_window(starts_at: datetime, ends_at: datetime, exclude_id: int | None = None, publishing: bool = False) -> None:
    if ends_at <= starts_at:
        raise HttpError(422, "เวลาจบต้องอยู่หลังเวลาเริ่ม")
    if publishing:
        clashes = overlapping(starts_at, ends_at, exclude_id)
        if clashes:
            names = ", ".join(c.name for c in clashes)
            raise HttpError(422, f"ช่วงเวลานี้ชนกับแคมเปญที่เผยแพร่แล้ว: {names}")


def check_publishable(c: Campaign) -> None:
    """Everything the shop needs must be present before a campaign goes live."""
    problems = []
    if c.hero_kind in (Campaign.HeroKind.IMAGE, Campaign.HeroKind.ANIMATION) and not c.hero_image:
        problems.append("ยังไม่มีรูปส่วนหัว")
    if c.hero_kind == Campaign.HeroKind.ANIMATION and not c.hero_poster:
        problems.append("ยังไม่มีภาพปกของภาพเคลื่อนไหว")
    if c.hero_kind == Campaign.HeroKind.VIDEO:
        if not c.hero_video:
            problems.append("ยังไม่มีไฟล์วิดีโอ")
        if not c.hero_poster:
            problems.append("ยังไม่มีภาพปกของวิดีโอ")
    if c.bar_enabled and not c.bar_text.strip():
        problems.append("เปิดแถบประกาศแล้วต้องมีข้อความ")
    if problems:
        raise HttpError(422, "เผยแพร่ไม่ได้: " + " · ".join(problems))


def poster_from_first_frame(upload) -> ContentFile:
    """A still JPEG of the first frame of a GIF or WebP, so the shop has something to show before it loads."""
    try:
        with Image.open(upload) as im:
            im.seek(0)
            frame = im.convert("RGB")
    except (UnidentifiedImageError, OSError):
        raise HttpError(422, "ไฟล์นี้ไม่ใช่ภาพเคลื่อนไหว") from None
    buf = io.BytesIO()
    frame.save(buf, format="JPEG", quality=85)
    upload.seek(0)
    return ContentFile(buf.getvalue(), name="poster.jpg")


VIDEO_MAGIC = {"mp4": (4, b"ftyp"), "webm": (0, b"\x1a\x45\xdf\xa3")}


def check_video(upload, max_bytes: int) -> str:
    """MP4 or WebM within the size limit. Judged by the file's first bytes, never by its name. Returns the extension."""
    if upload.size > max_bytes:
        raise HttpError(422, f"วิดีโอใหญ่เกิน {max_bytes // (1024 * 1024)} MB")
    head = upload.read(12)
    upload.seek(0)
    for ext, (offset, magic) in VIDEO_MAGIC.items():
        if head[offset:offset + len(magic)] == magic:
            return f".{ext}"
    raise HttpError(422, "รองรับเฉพาะวิดีโอ MP4 หรือ WebM")


COUNTED_ORDER_STATUSES = ("paid", "packing", "shipped", "done")   # money is in and not cancelled, as in the promotion report


def campaign_orders(c: Campaign):
    """Orders placed while the campaign was running, paid and not cancelled."""
    from maehai.orders.models import Order

    return Order.objects.filter(status__in=COUNTED_ORDER_STATUSES, created_at__gte=c.starts_at, created_at__lt=effective_end(c))


def safe_redirect(url: str) -> str:
    """Only our own paths and https links may be the target of a campaign button; anything else goes home."""
    if url.startswith("/") and not url.startswith("//"):
        return url
    if url.startswith("https://"):
        return url
    return "/"
