"""Public endpoints that receive the shop's usage numbers.

All three answer 204 and never say why something was dropped, so nobody can probe what is accepted. They read the
body themselves (text/plain or JSON) because `navigator.sendBeacon` sends text/plain, which needs no CORS preflight.
"""
import json
import math
import re

from django.conf import settings
from django.db.models import F
from django.utils import timezone
from ninja import Router

from maehai.core import ratelimit

from .models import ConsentCount, WebEvent, WebPageCount

router = Router(tags=["analytics"])

KINDS = {"page_view", "product_view", "add_to_cart", "cart_view", "checkout_start", "search", "web_vital"}
PAGE_TYPES = {"home", "products", "product", "cart", "checkout", "order", "track", "other"}
DEVICES = {"mobile", "tablet", "desktop"}
MAX_BATCH = 20
BOT = re.compile(r"bot|crawl|spider|headless|lighthouse|prerender|preview|monitor|curl|wget|python-requests|httpclient", re.I)
HEX = re.compile(r"^[a-f0-9]{16,32}$")
TOKEN = re.compile(r"^[a-z0-9_-]{1,40}$")
VERSION = re.compile(r"^[A-Za-z0-9._-]{1,40}$")
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
ORDER_PATH = re.compile(r"^/orders/[^/]+")


def clean_path(raw) -> str:
    """The page, without the query or fragment (they can hold order tokens), and with an order number replaced."""
    if not isinstance(raw, str):
        return ""
    path = raw.split("?", 1)[0].split("#", 1)[0][:120]
    if not path.startswith("/"):
        return ""
    return ORDER_PATH.sub("/orders/:number", path)


def clean_source(raw) -> str:
    s = raw.strip().lower() if isinstance(raw, str) else ""
    return s if TOKEN.match(s) else ""


def _number(raw):
    if isinstance(raw, bool) or not isinstance(raw, (int, float)) or not math.isfinite(raw):
        return None
    return float(raw)


def _body(request):
    try:
        data = json.loads(request.body.decode("utf-8") or "null")
    except (ValueError, UnicodeDecodeError):
        return None
    return data


def _is_bot(request) -> bool:
    return bool(BOT.search(request.META.get("HTTP_USER_AGENT", ""))) or not request.META.get("HTTP_USER_AGENT")


def _event(raw: dict) -> dict | None:
    kind = raw.get("kind")
    visitor = raw.get("v")
    if kind not in KINDS or not isinstance(visitor, str) or not HEX.match(visitor):
        return None
    slug = raw.get("slug") if isinstance(raw.get("slug"), str) and SLUG.match(raw.get("slug", "")) else ""
    name = raw.get("name") if isinstance(raw.get("name"), str) else ""
    qty = raw.get("qty")
    return {
        "visitor": visitor, "kind": kind, "path": clean_path(raw.get("path")), "slug": slug[:120],
        "name": name.strip().lower()[:40], "value": _number(raw.get("value")),
        "qty": qty if isinstance(qty, int) and not isinstance(qty, bool) and 1 <= qty <= 99 else None,
        "device": raw.get("device") if raw.get("device") in DEVICES else "",
        "source": clean_source(raw.get("src")) or "direct",
        "design_version": raw.get("ver") if isinstance(raw.get("ver"), str) and VERSION.match(raw["ver"]) else "",
    }


@router.post("/events", response={204: None})
def events(request):
    """A batch of up to 20 events from a visitor who agreed to be measured."""
    ratelimit.hit("analytics_ip", ratelimit.client_ip(request))
    data = _body(request)
    items = data.get("events") if isinstance(data, dict) else data
    if _is_bot(request) or not isinstance(items, list) or not items:
        return 204, None
    rows = [e for e in (_event(i) for i in items[:MAX_BATCH] if isinstance(i, dict)) if e]
    if rows:
        ratelimit.hit("analytics_visitor", rows[0]["visitor"])
        WebEvent.objects.bulk_create([WebEvent(**r) for r in rows])
    return 204, None


@router.post("/consent", response={204: None})
def consent(request):
    """Counts one answer to the consent banner. Stores a number per day, nothing about who answered."""
    ratelimit.hit("analytics_ip", ratelimit.client_ip(request))
    data = _body(request)
    choice = data.get("choice") if isinstance(data, dict) else None
    if choice in ("allow", "deny") and not _is_bot(request):
        _bump(ConsentCount, date=timezone.localdate(), choice=choice)
    return 204, None


@router.post("/count", response={204: None})
def count(request):
    """Counts one page view by kind of page. Off unless ANALYTICS_COUNT_WITHOUT_CONSENT is set."""
    ratelimit.hit("analytics_ip", ratelimit.client_ip(request))
    data = _body(request)
    page = data.get("type") if isinstance(data, dict) else None
    if settings.ANALYTICS_COUNT_WITHOUT_CONSENT and page in PAGE_TYPES and not _is_bot(request):
        _bump(WebPageCount, date=timezone.localdate(), page_type=page)
    return 204, None


def _bump(model, **key):
    obj, created = model.objects.get_or_create(**key, defaults={"count": 1})
    if not created:
        model.objects.filter(pk=obj.pk).update(count=F("count") + 1)
