"""Usage numbers from the shop (docs/specs/web-analytics.md, phase 1)."""
import json
from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from maehai.analytics.models import ConsentCount, WebEvent, WebPageCount
from maehai.orders.models import Order

pytestmark = pytest.mark.django_db

V = "a1b2c3d4e5f60718a1b2c3d4e5f60718"
UA = {"HTTP_USER_AGENT": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0) AppleWebKit/605.1.15 Mobile/15E148"}


def send(client, path, body, ua=UA, raw=False):
    """Posts the way navigator.sendBeacon does: a text/plain body."""
    data = body if raw else json.dumps(body)
    return client.post(path, data, content_type="text/plain", **ua)


def ev(**over):
    return {"kind": "page_view", "v": V, "path": "/", "device": "mobile", "src": "facebook", "ver": "2026-10", **over}


def test_events_are_stored_with_only_the_allowed_fields(client):
    r = send(client, "/api/analytics/events", [ev(path="/products?q=หมูยอ&t=SECRET"),
        ev(kind="product_view", slug="moo-yo-black-pepper", path="/products/moo-yo-black-pepper"),
        ev(kind="add_to_cart", slug="moo-yo-black-pepper", qty=2, value=17000),
        ev(kind="web_vital", name="LCP", value=2300.5),
        ev(kind="search", name="  หมูยอ ", value=3)])
    assert r.status_code == 204
    rows = {e.kind: e for e in WebEvent.objects.all()}
    assert set(rows) == {"page_view", "product_view", "add_to_cart", "web_vital", "search"}
    assert rows["page_view"].path == "/products"                                # the query is dropped
    assert rows["add_to_cart"].qty == 2 and rows["add_to_cart"].value == 17000
    assert rows["web_vital"].name == "lcp" and rows["web_vital"].value == 2300.5
    assert rows["search"].name == "หมูยอ"
    assert all(e.visitor == V and e.device == "mobile" and e.source == "facebook" and e.design_version == "2026-10" for e in rows.values())


def test_order_numbers_and_tokens_never_reach_the_table(client):
    send(client, "/api/analytics/events", [ev(path="/orders/MH-2569-000001?t=abc123", name="MH-2569-000001")])
    e = WebEvent.objects.get()
    assert e.path == "/orders/:number"
    assert "000001" not in json.dumps({f.name: str(getattr(e, f.name)) for f in e._meta.fields if f.name != "name"})


def test_unknown_fields_and_bad_values_are_dropped(client):
    send(client, "/api/analytics/events", [
        ev(phone="0812345678", customer_name="สมชาย", ip="1.2.3.4", address="x"),     # extra keys are ignored
        ev(kind="steal_cookies"),                                                      # unknown kind
        ev(v="not-hex"),                                                               # bad visitor id
        ev(src="javascript:alert(1)", device="toaster", ver="bad version!", qty=500, slug="Not A Slug", value="x"),
    ])
    rows = list(WebEvent.objects.all())
    assert len(rows) == 2                                                              # the first and the last
    assert not hasattr(rows[0], "phone")
    bad = rows[1]
    assert (bad.source, bad.device, bad.design_version, bad.qty, bad.slug, bad.value) == ("direct", "", "", None, "", None)


def test_garbage_and_bots_are_ignored_with_the_same_answer(client):
    for body in ["not json", "{}", "[]", '{"events": 5}', "null"]:
        assert send(client, "/api/analytics/events", body, raw=True).status_code == 204
    for agent in ["Googlebot/2.1", "Mozilla/5.0 HeadlessChrome/120", "Chrome-Lighthouse", "curl/8.0", ""]:
        assert send(client, "/api/analytics/events", [ev()], ua={"HTTP_USER_AGENT": agent}).status_code == 204
    assert WebEvent.objects.count() == 0


def test_a_batch_is_capped_at_twenty(client):
    send(client, "/api/analytics/events", [ev() for _ in range(35)])
    assert WebEvent.objects.count() == 20


def test_the_ip_address_is_not_stored(client):
    send(client, "/api/analytics/events", [ev()], ua={**UA, "REMOTE_ADDR": "203.0.113.77"})
    e = WebEvent.objects.get()
    assert all("203.0.113.77" not in str(getattr(e, f.name)) for f in e._meta.fields)


def test_rate_limit(client, settings):
    settings.RATE_LIMIT_ENABLED = True
    settings.RATE_LIMITS = {**settings.RATE_LIMITS, "analytics_ip": (3, 60)}
    codes = [send(client, "/api/analytics/events", [ev()]).status_code for _ in range(5)]
    assert codes == [204, 204, 204, 429, 429]


def test_consent_answers_are_counted_without_any_id(client):
    for choice in ["allow", "allow", "deny", "maybe"]:
        send(client, "/api/analytics/consent", {"choice": choice})
    counts = {c.choice: c.count for c in ConsentCount.objects.all()}
    assert counts == {"allow": 2, "deny": 1}
    assert {f.name for f in ConsentCount._meta.fields} == {"id", "date", "choice", "count"}


def test_page_counter_is_off_until_the_owner_turns_it_on(client, settings):
    send(client, "/api/analytics/count", {"type": "home"})
    assert WebPageCount.objects.count() == 0
    settings.ANALYTICS_COUNT_WITHOUT_CONSENT = True
    for t in ["home", "home", "product", "nonsense"]:
        send(client, "/api/analytics/count", {"type": t})
    assert {c.page_type: c.count for c in WebPageCount.objects.all()} == {"home": 2, "product": 1}


def test_order_keeps_the_source_and_visitor_only_when_they_look_right(client, place):
    r = place(traffic_source="facebook", visitor_ref=V)
    assert r.status_code == 201
    o = Order.objects.get(number=r.json()["number"])
    assert (o.traffic_source, o.visitor_ref) == ("facebook", V)
    r = place(traffic_source="http://evil.example/?x=1", visitor_ref="0812345678")
    assert r.status_code == 201
    o = Order.objects.get(number=r.json()["number"])
    assert (o.traffic_source, o.visitor_ref) == ("", "")
    r = place()                                                      # visitors who did not agree send neither
    assert Order.objects.get(number=r.json()["number"]).visitor_ref == ""


def test_old_events_are_pruned(client, settings):
    send(client, "/api/analytics/events", [ev()])
    send(client, "/api/analytics/events", [ev(kind="cart_view")])
    WebEvent.objects.filter(kind="cart_view").update(created_at=timezone.now() - timedelta(days=settings.WEB_EVENT_RETENTION_DAYS + 1))
    call_command("prune_web_events")
    assert list(WebEvent.objects.values_list("kind", flat=True)) == ["page_view"]
    call_command("prune_web_events")                                 # safe to repeat
    assert WebEvent.objects.count() == 1
