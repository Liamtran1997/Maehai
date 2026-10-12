import base64
import hashlib
import hmac
import json
from datetime import timedelta
from urllib.parse import unquote

import pytest
from django.utils import timezone

from maehai.notifications.delivery import deliver_pending
from maehai.notifications.line import LineError
from maehai.notifications.models import Outbox
from maehai.orders.models import Order
from maehai.orders.serializers import line_link_url

pytestmark = pytest.mark.django_db
JSON = "application/json"
SECRET = "test-secret"


class FakeLine:
    pushed: list = []
    replies: list = []
    fail_with: LineError | None = None

    def push(self, to, text, retry_key):
        if FakeLine.fail_with:
            raise FakeLine.fail_with
        FakeLine.pushed.append((to, text, retry_key))

    def reply(self, token, text):
        FakeLine.replies.append((token, text))


@pytest.fixture(autouse=True)
def line(settings):
    FakeLine.pushed, FakeLine.replies, FakeLine.fail_with = [], [], None
    settings.LINE_CLIENT = f"{__name__}.FakeLine"
    settings.LINE_CHANNEL_ACCESS_TOKEN = "token"
    settings.LINE_CHANNEL_SECRET = SECRET
    settings.LINE_STAFF_IDS = ["Cstaffgroup"]


def sign(body: bytes) -> str:
    return base64.b64encode(hmac.new(SECRET.encode(), body, hashlib.sha256).digest()).decode()


def webhook(client, text, user="Ucustomer", signature=None, **src):
    body = json.dumps({"events": [{"type": "message", "replyToken": "rt", "source": {"userId": user, **src},
                                   "message": {"type": "text", "text": text}}]}).encode()
    return client.post("/api/line/webhook", body, content_type=JSON, HTTP_X_LINE_SIGNATURE=signature or sign(body))


def link(client, number):
    o = Order.objects.get(number=number)
    return webhook(client, f"{o.number} รหัส {o.line_link_code}")


def kinds(**f):
    return list(Outbox.objects.filter(**f).values_list("kind", flat=True))


# ---------- staff alerts ----------
def test_new_order_alerts_staff(place):
    place()
    row = Outbox.objects.get()
    assert (row.audience, row.recipient, row.kind) == ("staff", "Cstaffgroup", "order_created")
    assert "รอลูกค้าชำระเงิน" in row.text and "/orders/MH-" in row.text


def test_carrier_order_tells_staff_to_quote(place):
    place(shipping_method="cargo-ubon")
    assert "ต้องแจ้งค่าจัดส่ง" in Outbox.objects.get().text


def test_each_staff_recipient_gets_a_message(place, settings):
    settings.LINE_STAFF_IDS = ["U1", "U2", "C3"]
    place()
    assert sorted(Outbox.objects.values_list("recipient", flat=True)) == ["C3", "U1", "U2"]


def test_no_staff_configured_means_no_staff_rows(place, settings):
    settings.LINE_STAFF_IDS = []
    place()
    assert Outbox.objects.count() == 0


def test_slip_alerts_staff(client, place, settings):
    from tests.test_payments import charge, upload  # reuse helpers

    o = place().json()
    charge(client, o); upload(client, o)
    assert "slip_submitted" in kinds()


# ---------- connecting a customer's LINE ----------
def test_link_url_matches_what_the_webhook_parses(client, place, settings):
    o = Order.objects.get(number=place().json()["number"])
    text = unquote(line_link_url(o).split("/?", 1)[1])
    assert webhook(client, text).status_code == 200
    o.refresh_from_db()
    assert o.line_user_id == "Ucustomer"
    assert FakeLine.replies and "เชื่อมต่อ LINE" in FakeLine.replies[0][1]


def test_order_api_exposes_link_state(client, place):
    o = place().json()
    assert o["line_linked"] is False and o["line_link_url"].startswith("https://line.me/R/oaMessage/@maehai/?")
    link(client, o["number"])
    again = client.get(f"/api/orders/{o['number']}", {"token": o["token"]}).json()
    assert again["line_linked"] is True and again["line_link_url"] is None


def test_wrong_code_does_not_link(client, place):
    o = place().json()
    webhook(client, f"{o['number']} รหัส AAAAAAAA")
    assert Order.objects.get(number=o["number"]).line_user_id == ""
    assert FakeLine.replies  # told how to do it properly


def test_bad_signature_is_rejected(client, place):
    o = place().json()
    r = webhook(client, f"{o['number']} รหัส X", signature="bad")
    assert r.status_code == 401 and Order.objects.get(number=o["number"]).line_user_id == ""


def test_unconfigured_secret_rejects_everything(client, settings):
    settings.LINE_CHANNEL_SECRET = ""
    assert client.post("/api/line/webhook", b"{}", content_type=JSON, HTTP_X_LINE_SIGNATURE=sign(b"{}")).status_code == 401


def test_id_command_reveals_group_id(client):
    webhook(client, "/id", groupId="Cgroup123")
    assert FakeLine.replies == [("rt", "ID: Cgroup123")]


def test_ordinary_chat_is_ignored(client, place):
    webhook(client, "สวัสดีครับ มีหมูยอไหม")
    assert FakeLine.replies == []


# ---------- customer messages ----------
def test_unlinked_customer_gets_nothing(client, staff_client, place):
    o = place(shipping_method="cargo-ubon").json()
    staff_client.post(f"/api/admin/orders/{o['number']}/fee", {"fee_satang": 12000}, content_type=JSON)
    assert kinds(audience="customer") == []


def test_full_journey_messages(client, staff_client, place):
    o = place(shipping_method="cargo-ubon").json()
    link(client, o["number"])
    n = o["number"]
    staff_client.post(f"/api/admin/orders/{n}/fee", {"fee_satang": 12000}, content_type=JSON)
    pid = client.post(f"/api/payments/{n}/charge?token={o['token']}").json()["id"]
    staff_client.post(f"/api/admin/payments/{pid}/confirm")
    staff_client.post(f"/api/admin/orders/{n}/status", {"status": "packing"}, content_type=JSON)
    staff_client.post(f"/api/admin/orders/{n}/status", {"status": "shipped", "tracking_ref": "UB-777"}, content_type=JSON)
    assert kinds(audience="customer") == ["fee_quoted", "paid", "shipped"]   # packing is not worth a push

    msgs = {r.kind: r.text for r in Outbox.objects.filter(audience="customer")}
    assert "฿120.00" in msgs["fee_quoted"] and f"/orders/{n}?t={o['token']}" in msgs["fee_quoted"]
    assert "UB-777" in msgs["shipped"] and "สหฯอุบลคาร์โก้" in msgs["shipped"]


def test_reject_and_cancel_messages(client, staff_client, place):
    from tests.test_payments import charge, upload

    o = place().json()
    link(client, o["number"])
    charge(client, o)
    pid = upload(client, o).json()["id"]
    staff_client.post(f"/api/admin/payments/{pid}/reject", {"reason": "ยอดไม่ตรง"}, content_type=JSON)
    staff_client.post(f"/api/admin/orders/{o['number']}/status", {"status": "cancelled"}, content_type=JSON)
    assert kinds(audience="customer") == ["slip_rejected", "cancelled"]
    assert "ยอดไม่ตรง" in Outbox.objects.get(kind="slip_rejected").text


# ---------- delivery ----------
def test_deliver_marks_sent_with_stable_retry_key(place):
    place()
    row = Outbox.objects.get()
    assert deliver_pending() == {"sent": 1, "failed": 0, "retry": 0, "skipped": 0}
    row.refresh_from_db()
    assert row.status == "sent" and row.sent_at and FakeLine.pushed[0][2] == str(row.retry_key)
    assert deliver_pending()["sent"] == 0     # nothing is sent twice


def test_transient_failure_retries_with_backoff_then_gives_up(place, settings):
    place()
    row = Outbox.objects.get()
    FakeLine.fail_with = LineError("HTTP 503", retryable=True)
    now = timezone.now()
    for attempt in range(1, settings.NOTIFY_MAX_ATTEMPTS):
        assert deliver_pending(now=now)["retry"] == 1
        row.refresh_from_db()
        assert row.attempts == attempt and row.send_after == now + timedelta(minutes=2 ** attempt)
        assert deliver_pending(now=now)["retry"] == 0   # not due yet
        now = row.send_after
    assert deliver_pending(now=now)["failed"] == 1
    row.refresh_from_db()
    assert row.status == "failed" and "503" in row.last_error


def test_permanent_failure_is_not_retried(place):
    place()
    FakeLine.fail_with = LineError("HTTP 400: blocked", retryable=False)
    assert deliver_pending()["failed"] == 1
    assert Outbox.objects.get().attempts == 1


def test_retry_after_failure_succeeds_and_reuses_key(place):
    place()
    row = Outbox.objects.get()
    FakeLine.fail_with = LineError("network", retryable=True)
    deliver_pending()
    FakeLine.fail_with = None
    deliver_pending(now=timezone.now() + timedelta(minutes=10))
    row.refresh_from_db()
    assert row.status == "sent" and FakeLine.pushed[0][2] == str(row.retry_key)


def test_unconfigured_line_skips_instead_of_piling_up(place, settings):
    settings.LINE_CHANNEL_ACCESS_TOKEN = ""
    place()
    assert deliver_pending()["skipped"] == 1
    assert Outbox.objects.get().status == "skipped" and FakeLine.pushed == []


def test_order_flow_survives_when_line_is_down(client, place):
    """Sending is separate from ordering: a LINE outage never fails an order."""
    FakeLine.fail_with = LineError("down", retryable=True)
    assert place().status_code == 201
