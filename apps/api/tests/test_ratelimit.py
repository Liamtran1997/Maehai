import pytest
from django.contrib.auth import get_user_model

from maehai.core import ratelimit
from tests.conftest import make_staff

pytestmark = pytest.mark.django_db
JSON = "application/json"


@pytest.fixture(autouse=True)
def on(settings):
    settings.RATE_LIMIT_ENABLED = True
    settings.RATE_LIMITS = {**settings.RATE_LIMITS,
        "order_create_ip": (3, 3600), "order_create_phone": (2, 86400), "lookup_ip": (4, 600),
        "lookup_fail_ip": (3, 900), "lookup_fail_order": (2, 900), "token_fail_ip": (3, 900),
        "login_fail_ip": (3, 900), "login_fail_user": (2, 900), "charge_order": (2, 3600),
        "slip_order": (1, 3600), "slip_ip": (5, 3600)}


@pytest.fixture
def clock(monkeypatch):
    t = {"now": 1_000_000.0}
    monkeypatch.setattr(ratelimit, "_now", lambda: t["now"])
    return t


def post(client, url, data, ip="10.0.0.1", **extra):
    return client.post(url, data, content_type=JSON, REMOTE_ADDR=ip, **extra)


# ---------- unit ----------
def test_hit_blocks_after_limit_and_reports_retry_after(clock):
    for _ in range(3):
        ratelimit.hit("order_create_ip", "a")
    with pytest.raises(ratelimit.RateLimited) as e:
        ratelimit.hit("order_create_ip", "a")
    assert 1 <= e.value.retry_after <= 3600
    ratelimit.hit("order_create_ip", "someone-else")      # other identities are unaffected


def test_window_rolls_over(clock):
    for _ in range(3):
        ratelimit.hit("order_create_ip", "a")
    clock["now"] += 3600
    ratelimit.hit("order_create_ip", "a")                  # fresh window


def test_failures_only_block_after_enough_failures_and_can_be_forgiven(clock):
    ratelimit.failed("lookup_fail_order", "MH-1"); ratelimit.blocked("lookup_fail_order", "MH-1")
    ratelimit.failed("lookup_fail_order", "MH-1")
    with pytest.raises(ratelimit.RateLimited):
        ratelimit.blocked("lookup_fail_order", "MH-1")
    ratelimit.forgive("lookup_fail_order", "MH-1")
    ratelimit.blocked("lookup_fail_order", "MH-1")


def test_disabled_means_no_limit(settings, clock):
    settings.RATE_LIMIT_ENABLED = False
    for _ in range(50):
        ratelimit.hit("order_create_ip", "a")


def test_client_ip_only_trusts_forwarded_header_from_our_proxies(rf, settings):
    req = rf.get("/", HTTP_X_FORWARDED_FOR="6.6.6.6, 1.1.1.1", REMOTE_ADDR="10.9.9.9")
    assert ratelimit.client_ip(req) == "10.9.9.9"          # no proxies configured: header ignored
    settings.TRUSTED_PROXY_COUNT = 1
    assert ratelimit.client_ip(req) == "1.1.1.1"           # the entry our proxy added, not the forged leftmost one
    settings.TRUSTED_PROXY_COUNT = 3
    assert ratelimit.client_ip(req) == "10.9.9.9"          # header shorter than expected: fall back to the socket


# ---------- endpoints ----------
def test_order_creation_limited_per_ip(client, order_payload, seeded):
    for phone in ("0811111111", "0822222222", "0833333333"):
        assert post(client, "/api/orders", order_payload(phone=phone)).status_code == 201
    r = post(client, "/api/orders", order_payload(phone="0844444444"))
    assert r.status_code == 429 and r["Retry-After"] and r.json()["retry_after"] >= 1
    assert "ถี่เกินไป" in r.json()["detail"]
    assert post(client, "/api/orders", order_payload(phone="0844444444"), ip="10.9.9.9").status_code == 201   # other IPs unaffected


def test_order_creation_limited_per_phone_across_ips(client, order_payload, seeded):
    for i in range(2):
        assert post(client, "/api/orders", order_payload(), ip=f"10.0.1.{i}").status_code == 201
    assert post(client, "/api/orders", order_payload(), ip="10.0.1.99").status_code == 429


def test_lookup_guessing_is_locked_per_order_and_per_ip(client, order_payload, seeded):
    n = post(client, "/api/orders", order_payload()).json()["number"]
    wrong = {"number": n, "phone": "0899999999"}
    assert post(client, "/api/orders/lookup", wrong).status_code == 404
    assert post(client, "/api/orders/lookup", wrong).status_code == 404
    # two failures on this order: even from a fresh IP the right phone is now refused until the window passes
    assert post(client, "/api/orders/lookup", {"number": n, "phone": "0812345678"}, ip="10.0.2.2").status_code == 429


def test_successful_lookup_forgives_earlier_typos(client, order_payload, seeded):
    n = post(client, "/api/orders", order_payload()).json()["number"]
    assert post(client, "/api/orders/lookup", {"number": n, "phone": "0899999999"}, ip="10.0.3.1").status_code == 404
    assert post(client, "/api/orders/lookup", {"number": n, "phone": "0812345678"}, ip="10.0.3.2").status_code == 200
    assert post(client, "/api/orders/lookup", {"number": n, "phone": "0899999999"}, ip="10.0.3.3").status_code == 404  # counter was reset


def test_wrong_tokens_are_throttled_but_right_token_from_other_ip_is_fine(client, order_payload, seeded):
    o = post(client, "/api/orders", order_payload()).json()
    for _ in range(3):
        assert client.get(f"/api/orders/{o['number']}", {"token": "x"}, REMOTE_ADDR="10.0.4.1").status_code == 404
    assert client.get(f"/api/orders/{o['number']}", {"token": o["token"]}, REMOTE_ADDR="10.0.4.1").status_code == 429
    assert client.get(f"/api/orders/{o['number']}", {"token": o["token"]}, REMOTE_ADDR="10.0.4.2").status_code == 200


def test_login_brute_force_is_throttled(client, db):
    make_staff("owner", "owner")
    bad = {"username": "owner", "password": "nope"}
    assert post(client, "/api/auth/login", bad, ip="10.0.5.1").status_code == 401
    assert post(client, "/api/auth/login", bad, ip="10.0.5.2").status_code == 401
    # the account is locked from every IP, including with the right password
    good = {"username": "owner", "password": "pw-test-123"}
    assert post(client, "/api/auth/login", good, ip="10.0.5.3").status_code == 429


def test_login_ip_limit_applies_across_usernames(client, db):
    for i in range(3):
        assert post(client, "/api/auth/login", {"username": f"u{i}", "password": "x"}, ip="10.0.6.1").status_code == 401
    assert post(client, "/api/auth/login", {"username": "u9", "password": "x"}, ip="10.0.6.1").status_code == 429


def test_login_success_clears_user_failures(client, db):
    make_staff("owner", "owner")
    post(client, "/api/auth/login", {"username": "Owner", "password": "bad"}, ip="10.0.7.1")   # case-insensitive counter
    assert post(client, "/api/auth/login", {"username": "owner", "password": "pw-test-123"}, ip="10.0.7.2").status_code == 200
    assert post(client, "/api/auth/login", {"username": "owner", "password": "bad"}, ip="10.0.7.3").status_code == 401
    assert post(client, "/api/auth/login", {"username": "owner", "password": "bad"}, ip="10.0.7.4").status_code == 401


def test_charge_and_slip_limits_per_order(client, order_payload, seeded):
    from tests.test_payments import png

    o = post(client, "/api/orders", order_payload()).json()
    url = f"/api/payments/{o['number']}/charge?token={o['token']}"
    assert client.post(url).status_code == 200 and client.post(url).status_code == 200
    assert client.post(url).status_code == 429
    s = f"/api/payments/{o['number']}/slip?token={o['token']}"
    assert client.post(s, {"slip": png()}).status_code == 200
    assert client.post(s, {"slip": png()}).status_code == 429


def test_catalog_is_not_limited(client, seeded):
    for _ in range(40):
        assert client.get("/api/catalog/products").status_code == 200
