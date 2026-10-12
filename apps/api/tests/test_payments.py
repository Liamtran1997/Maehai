from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from maehai.orders.models import Order
from maehai.payments.models import Payment
from maehai.payments.providers import SlipResult

pytestmark = pytest.mark.django_db
JSON = "application/json"


def png(name="slip.png", ctype="image/png") -> SimpleUploadedFile:
    buf = BytesIO()
    Image.new("RGB", (4, 4), "white").save(buf, "PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type=ctype)


@pytest.fixture
def order(place):
    return place().json()  # pickup: waiting_payment, total 205.00


def charge(client, o):
    return client.post(f"/api/payments/{o['number']}/charge?token={o['token']}")


def upload(client, o, f=None):
    return client.post(f"/api/payments/{o['number']}/slip?token={o['token']}", {"slip": f or png()})


def test_charge_makes_promptpay_qr_with_exact_amount(client, order):
    r = charge(client, order)
    assert r.status_code == 200, r.content
    p = r.json()
    assert p["status"] == "pending" and p["amount_satang"] == 20500
    assert p["qr_payload"].startswith("000201") and "205.00" in p["qr_payload"] and "0066812345678" in p["qr_payload"]


def test_charge_is_idempotent_while_live(client, order):
    assert charge(client, order).json()["id"] == charge(client, order).json()["id"]
    assert Payment.objects.count() == 1


def test_expired_qr_is_replaced(client, order):
    from datetime import timedelta
    from django.utils import timezone

    first = charge(client, order).json()["id"]
    Payment.objects.filter(pk=first).update(expires_at=timezone.now() - timedelta(seconds=1))
    second = charge(client, order).json()
    assert second["id"] != first and second["status"] == "pending"
    assert Payment.objects.get(pk=first).status == "expired"


def test_cannot_charge_before_fee_is_quoted(client, place):
    o = place(shipping_method="cargo-ubon").json()
    assert charge(client, o).status_code == 409


def test_wrong_token_cannot_charge(client, order):
    assert client.post(f"/api/payments/{order['number']}/charge?token=nope").status_code == 404


def test_missing_promptpay_config(client, order, settings):
    settings.PROMPTPAY_ID = ""
    assert charge(client, order).status_code == 503


def test_slip_then_staff_confirms_order_becomes_paid(client, staff_client, order):
    charge(client, order)
    r = upload(client, order)
    assert r.status_code == 200 and r.json()["status"] == "slip_submitted" and r.json()["slip_url"]
    assert Order.objects.get(number=order["number"]).status == "waiting_payment"   # not paid until someone confirms

    pid = r.json()["id"]
    assert client.post(f"/api/admin/payments/{pid}/confirm").status_code == 401     # customers cannot confirm
    assert staff_client.post(f"/api/admin/payments/{pid}/confirm").json()["status"] == "confirmed"
    assert staff_client.post(f"/api/admin/payments/{pid}/confirm").status_code == 200  # idempotent
    o = Order.objects.get(number=order["number"])
    assert o.status == "paid"
    assert o.events.filter(kind="status", actor="owner").count() == 1


def test_paid_order_cannot_be_charged_again(client, staff_client, order):
    charge(client, order)
    pid = upload(client, order).json()["id"]
    staff_client.post(f"/api/admin/payments/{pid}/confirm")
    assert charge(client, order).status_code == 409


def test_reject_lets_customer_try_again(client, staff_client, order):
    charge(client, order)
    pid = upload(client, order).json()["id"]
    r = staff_client.post(f"/api/admin/payments/{pid}/reject", {"reason": "ยอดไม่ตรง"}, content_type=JSON)
    assert r.json()["status"] == "rejected"
    again = charge(client, order).json()
    assert again["id"] != pid and again["status"] == "pending"


def test_slip_validation(client, order):
    charge(client, order)
    assert upload(client, order, SimpleUploadedFile("x.pdf", b"%PDF", content_type="application/pdf")).status_code == 422
    big = SimpleUploadedFile("big.png", b"0" * (5 * 1024 * 1024 + 1), content_type="image/png")
    assert upload(client, order, big).status_code == 422


def test_cannot_requote_after_slip_submitted(staff_client, client, place):
    o = place(shipping_method="cargo-ubon").json()
    staff_client.post(f"/api/admin/orders/{o['number']}/fee", {"fee_satang": 12000}, content_type=JSON)
    charge(client, o)
    upload(client, o)
    r = staff_client.post(f"/api/admin/orders/{o['number']}/fee", {"fee_satang": 9000}, content_type=JSON)
    assert r.status_code == 409


def test_requote_voids_unpaid_qr(staff_client, client, place):
    o = place(shipping_method="cargo-ubon").json()
    staff_client.post(f"/api/admin/orders/{o['number']}/fee", {"fee_satang": 12000}, content_type=JSON)
    first = charge(client, o).json()
    staff_client.post(f"/api/admin/orders/{o['number']}/fee", {"fee_satang": 9000}, content_type=JSON)
    second = charge(client, o).json()
    assert second["id"] != first["id"] and second["amount_satang"] == 20500 + 9000
    assert Payment.objects.get(pk=first["id"]).status == "expired"


class AutoApprove:
    def verify(self, payment):
        return SlipResult(ok=True)


class AutoReject:
    def verify(self, payment):
        return SlipResult(ok=False, detail="ยอดไม่ตรง")


def test_automatic_verifier_approves(client, order, settings):
    settings.SLIP_VERIFIER = f"{__name__}.AutoApprove"
    charge(client, order)
    assert upload(client, order).json()["status"] == "confirmed"
    assert Order.objects.get(number=order["number"]).status == "paid"


def test_automatic_verifier_rejects(client, order, settings):
    settings.SLIP_VERIFIER = f"{__name__}.AutoReject"
    charge(client, order)
    r = upload(client, order).json()
    assert r["status"] == "rejected" and r["reject_reason"] == "ยอดไม่ตรง"
    assert Order.objects.get(number=order["number"]).status == "waiting_payment"


def test_full_happy_path_to_done(client, staff_client, order):
    charge(client, order)
    staff_client.post(f"/api/admin/payments/{upload(client, order).json()['id']}/confirm")
    st = lambda s, **kw: staff_client.post(f"/api/admin/orders/{order['number']}/status", {"status": s, **kw}, content_type=JSON)
    assert st("packing").status_code == 200
    r = st("shipped", tracking_ref="UB-12345")
    assert r.json()["tracking_ref"] == "UB-12345"
    assert st("done").json()["status"] == "done"
    assert st("cancelled").status_code == 409
