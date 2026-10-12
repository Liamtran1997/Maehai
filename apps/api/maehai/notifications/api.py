"""LINE webhook. Customers connect LINE to an order by sending the prefilled message from the order page."""
import json
import re

from django.conf import settings
from django.http import HttpResponse
from django.utils.module_loading import import_string
from ninja import Router

from maehai.orders.models import Order

from . import texts
from .line import verify_signature

router = Router(tags=["line"])

RESTOCK_RE = re.compile(r"^แจ้งเตือนสินค้า\s+([A-Za-z0-9._-]{1,40})$")
LINK_RE = re.compile(r"(MH-\d{4}-\d{6})\s+(?:รหัส\s*)?([A-Z2-9]{8})", re.IGNORECASE)


def _handle_message(event: dict, client) -> None:
    text = (event.get("message") or {}).get("text", "").strip()
    token = event.get("replyToken")
    src = event.get("source") or {}

    # Staff helper: send "/id" in a chat or group to learn the ID to put in LINE_STAFF_IDS.
    if text.lower() == "/id":
        client.reply(token, f"ID: {src.get('groupId') or src.get('roomId') or src.get('userId', '?')}")
        return

    user_id = src.get("userId")
    r = RESTOCK_RE.match(text)
    if r and user_id:
        _handle_restock(r.group(1), user_id, token, client)
        return

    m = LINK_RE.search(text)
    if not m or not user_id:
        return  # ordinary chat with the shop: staff answer in LINE OA Manager, the bot stays quiet
    order = Order.objects.filter(number=m.group(1).upper(), line_link_code=m.group(2).upper()).first()
    if order is None:
        client.reply(token, texts.LINK_HELP)
        return
    order.line_user_id = user_id
    order.save(update_fields=["line_user_id", "updated_at"])
    client.reply(token, texts.link_ok(order))


def _handle_restock(sku: str, user_id: str, token: str, client) -> None:
    from maehai.catalog.models import ProductVariant
    from maehai.inventory.services import available_map, request_restock_alert

    v = ProductVariant.objects.select_related("product").filter(sku=sku, is_active=True, product__is_active=True).first()
    if v is None:
        client.reply(token, "ไม่พบสินค้านี้ ลองกดปุ่มจากหน้าสินค้าบนเว็บอีกครั้ง")
        return
    if (available_map([v.id]).get(v.id) or 0) > 0 or not v.track_stock:
        client.reply(token, texts.restock_in_stock(v))
        return
    request_restock_alert(v, user_id)
    client.reply(token, texts.restock_ok(v))


@router.post("/webhook")
def webhook(request):
    body = request.body
    if not verify_signature(body, request.headers.get("X-Line-Signature", "")):
        return HttpResponse(status=401)
    try:
        events = json.loads(body).get("events", [])
    except ValueError:
        return HttpResponse(status=400)
    client = import_string(settings.LINE_CLIENT)()
    for ev in events:
        if ev.get("type") == "message" and (ev.get("message") or {}).get("type") == "text":
            try:
                _handle_message(ev, client)
            except Exception:  # one bad event must not make LINE retry the whole batch forever
                import logging
                logging.getLogger(__name__).exception("LINE webhook event failed")
    return HttpResponse(status=200)
