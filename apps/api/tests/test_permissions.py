import re

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from maehai.core.models import AuditLog, StaffProfile
from maehai.core.permissions import PERMISSIONS, ROLES, PermissionAuth, permissions_of
from tests.conftest import login_as, make_staff

pytestmark = pytest.mark.django_db
JSON = "application/json"


# ================================================================ the matrix: every admin endpoint x every role
def admin_operations():
    """(method, path, perm) for every operation mounted under /api/admin/. perm None = any active staff member."""
    from config.api import api

    ops = []
    for prefix, router in api._routers:
        for path, pv in router.path_operations.items():
            for op in pv.operations:
                full = f"/api{prefix.rstrip('/')}{path}"
                if not full.startswith("/api/admin/"):
                    continue
                auths = [a for a in op.auth_callbacks if isinstance(a, PermissionAuth)]
                ops.append((op.methods[0], full, auths))
    return ops


def test_every_admin_endpoint_declares_exactly_one_permission():
    """The guard that keeps this safe over time: a new endpoint with no (or the wrong kind of) auth fails here."""
    ops = admin_operations()
    assert len(ops) >= 40, "route discovery broke"
    for method, path, auths in ops:
        assert len(auths) == 1, f"{method} {path} has no PermissionAuth: it would be open or unchecked"
        perm = auths[0].perm
        assert perm is None or perm in PERMISSIONS, f"{method} {path} names an unknown permission {perm!r}"


def test_role_definitions_are_consistent():
    assert ROLES["owner"]["permissions"] == set(PERMISSIONS)
    assert ROLES["manager"]["permissions"] == set(PERMISSIONS) - {"staff.manage"}
    assert all(r["permissions"] <= set(PERMISSIONS) for r in ROLES.values())
    assert [k for k, r in ROLES.items() if "staff.manage" in r["permissions"]] == ["owner"]
    # nobody except owner and manager can touch money settings
    assert [k for k, r in ROLES.items() if "pricing.manage" in r["permissions"]] == ["owner", "manager"]
    assert [k for k, r in ROLES.items() if "coupons.view" in r["permissions"]] == ["owner", "manager", "sales"]
    # warehouse and content never see payment slips
    assert "payments.review" not in ROLES["warehouse"]["permissions"] | ROLES["content"]["permissions"]


def concrete(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "999999", path)


def test_matrix_every_role_against_every_admin_endpoint():
    """Authentication runs before anything else, so for an endpoint needing perm P:
    a role without P must get exactly 403; a role with P must get anything but 401/403 (404/422 are fine: bad ids)."""
    clients = {role: login_as(make_staff(f"u-{role}", role).username) for role in ROLES}
    anon = Client()
    problems = []
    for method, path, auths in admin_operations():
        perm = auths[0].perm
        url = concrete(path)
        call = lambda c: getattr(c, method.lower())(url, **({"data": "{}", "content_type": JSON} if method in ("POST", "PUT") else {}))
        if call(anon).status_code != 401:
            problems.append(f"anonymous {method} {path} was not 401")
        for role, client in clients.items():
            allowed = perm is None or perm in ROLES[role]["permissions"]
            code = call(client).status_code
            if allowed and code in (401, 403):
                problems.append(f"{role} should be allowed {method} {path} ({perm}) but got {code}")
            if not allowed and code != 403:
                problems.append(f"{role} should be refused {method} {path} ({perm}) but got {code}")
    assert not problems, "\n".join(problems)


# ================================================================ role behaviour that depends on the request
def api(c, method, url, body=None):
    kw = {"content_type": JSON} if body is not None else {}
    return getattr(c, method)(url, body if body is not None else {}, **kw) if method in ("post", "put") else getattr(c, method)(url)


def test_who_you_are(as_role):
    me = as_role("sales").get("/api/auth/me").json()
    assert me["role"] == "sales" and me["role_label"] == "พนักงานขาย" and "payments.review" in me["permissions"]
    assert "pricing.manage" not in me["permissions"] and me["must_change_password"] is False


def test_staff_user_without_a_role_cannot_log_in(db):
    get_user_model().objects.create_user("norole", password="pw-test-123", is_staff=True)
    r = Client().post("/api/auth/login", {"username": "norole", "password": "pw-test-123"}, content_type=JSON)
    assert r.status_code == 401


def test_superuser_without_a_profile_counts_as_owner(db):
    get_user_model().objects.create_superuser("root", password="pw-test-123")
    c = login_as("root")
    assert c.get("/api/auth/me").json()["role"] == "owner" and c.get("/api/admin/staff").status_code == 200


def test_inactive_account_cannot_log_in(db):
    u = make_staff("gone", "sales")
    u.is_active = False
    u.save()
    assert Client().post("/api/auth/login", {"username": "gone", "password": "pw-test-123"}, content_type=JSON).status_code == 401


def test_cancelling_a_paid_order_needs_the_stronger_permission(as_role, staff_client, place, client):
    from tests.test_payments import charge

    def paid_order():
        o = place().json()
        pid = charge(client, o).json()["id"]
        staff_client.post(f"/api/admin/payments/{pid}/confirm")
        return o["number"]

    unpaid = place().json()["number"]
    paid = paid_order()
    sales, manager = as_role("sales"), as_role("manager")
    assert api(sales, "post", f"/api/admin/orders/{unpaid}/status", {"status": "cancelled"}).status_code == 200   # unpaid: fine
    assert api(sales, "post", f"/api/admin/orders/{paid}/status", {"status": "cancelled"}).status_code == 403     # money owed: no
    assert api(manager, "post", f"/api/admin/orders/{paid}/status", {"status": "cancelled"}).status_code == 200
    log = AuditLog.objects.get(action="order.cancel_paid")
    assert log.actor == "user-manager" and log.target == paid


def test_warehouse_can_ship_but_not_cancel_or_quote(as_role, staff_client, place, client):
    from tests.test_payments import charge

    wh = as_role("warehouse")
    o = place().json()
    n = o["number"]
    assert api(wh, "post", f"/api/admin/orders/{n}/status", {"status": "cancelled"}).status_code == 403
    assert api(wh, "post", f"/api/admin/orders/{n}/fee", {"fee_satang": 1000}).status_code == 403
    pid = charge(client, o).json()["id"]
    staff_client.post(f"/api/admin/payments/{pid}/confirm")
    assert api(wh, "post", f"/api/admin/orders/{n}/status", {"status": "packing"}).status_code == 200
    assert api(wh, "post", f"/api/admin/orders/{n}/status", {"status": "shipped", "tracking_ref": "T1"}).status_code == 200


def test_warehouse_sees_the_order_but_never_the_slip(as_role, staff_client, place, client):
    from tests.test_payments import charge, upload

    o = place().json()
    charge(client, o)
    pid = upload(client, o).json()["id"]
    detail = lambda c: c.get(f"/api/admin/orders/{o['number']}").json()
    assert detail(staff_client)["payment"]["slip_url"]                       # the owner sees it
    wh = as_role("warehouse")
    d = detail(wh)
    assert d["customer_name"] and d["items"] and d["payment"]["slip_url"] is None
    assert wh.get(f"/api/admin/payments/{pid}/slip").status_code == 403


def test_content_staff_edit_products_but_not_prices(as_role, seeded):
    content = as_role("content")
    p = next(x for x in content.get("/api/admin/catalog/products").json() if x["slug"] == "moo-yo-black-pepper")

    def body(**over):
        b = {"category_slug": p["category"]["slug"], "slug": p["slug"], "name": p["name"], "description": "เขียนใหม่",
             "variants": [{"label": v["label"], "sku": v["sku"], "price_satang": v["price_satang"]} for v in p["variants"]]}
        return {**b, **over}

    assert api(content, "put", f"/api/admin/catalog/products/{p['id']}", body()).status_code == 200      # text only
    dearer = body(variants=[{"label": v["label"], "sku": v["sku"], "price_satang": v["price_satang"] + 100} for v in p["variants"]])
    assert api(content, "put", f"/api/admin/catalog/products/{p['id']}", dearer).status_code == 403
    extra = body(variants=body()["variants"] + [{"label": "ยักษ์", "sku": "new-sku", "price_satang": 9000}])
    assert api(content, "put", f"/api/admin/catalog/products/{p['id']}", extra).status_code == 403       # a new size sets a price
    new_product = {**body(), "slug": "brand-new", "name": "ใหม่"}
    assert api(content, "post", "/api/admin/catalog/products", new_product).status_code == 403
    assert not AuditLog.objects.filter(action="price.change").exists()


def test_price_changes_are_audited_with_old_and_new(staff_client, seeded):
    p = next(x for x in staff_client.get("/api/admin/catalog/products").json() if x["slug"] == "naem-pork")
    body = {"category_slug": p["category"]["slug"], "slug": p["slug"], "name": p["name"],
            "variants": [{"label": v["label"], "sku": v["sku"], "price_satang": 7000} for v in p["variants"]]}
    assert api(staff_client, "put", f"/api/admin/catalog/products/{p['id']}", body).status_code == 200
    log = AuditLog.objects.get(action="price.change")
    assert log.actor == "owner" and log.target == "naem-pork" and "60 → 70" in log.detail


def test_promotions_and_coupons_are_manager_only_and_audited(as_role, staff_client, seeded):
    from datetime import timedelta
    from django.utils import timezone

    start = (timezone.now() - timedelta(hours=1)).isoformat()
    coupon = {"code": "PERM1", "name": "x", "kind": "amount", "value": 1000, "starts_at": start}
    assert api(as_role("sales"), "post", "/api/admin/coupons", coupon).status_code == 403
    assert api(as_role("content"), "post", "/api/admin/coupons", coupon).status_code == 403
    assert api(as_role("manager"), "post", "/api/admin/coupons", coupon).status_code == 201
    assert {"coupon.create"} <= set(AuditLog.objects.values_list("action", flat=True))
    assert as_role("sales").get("/api/admin/coupons").status_code == 200         # read-only for support staff
    assert as_role("warehouse").get("/api/admin/coupons").status_code == 403     # a coupon code is money: the warehouse never sees it
    assert as_role("content").get("/api/admin/coupons").status_code == 403


def test_only_reports_viewers_see_revenue_but_everyone_sees_the_todo_counts(as_role):
    wh = as_role("warehouse")
    assert wh.get("/api/admin/reports/summary").status_code == 403
    todo = wh.get("/api/admin/reports/todo")
    assert todo.status_code == 200 and set(todo.json()) >= {"slips_to_check", "to_pack", "low_stock"}


# ================================================================ managing staff
def new_staff(owner, **over):
    body = {"username": "somchai", "display_name": "สมชาย", "role": "sales", "password": "Temp-pass-4821"}
    return owner.post("/api/admin/staff", {**body, **over}, content_type=JSON)


def test_owner_creates_staff_who_must_change_the_temporary_password(staff_client):
    r = new_staff(staff_client)
    assert r.status_code == 201 and r.json()["must_change_password"] is True and r.json()["role_label"] == "พนักงานขาย"
    c = login_as("somchai", "Temp-pass-4821")
    assert c.get("/api/auth/me").json()["must_change_password"] is True
    blocked = c.get("/api/admin/orders")
    assert blocked.status_code == 403 and "เปลี่ยนรหัสผ่าน" in blocked.json()["detail"]
    assert c.get("/api/auth/me").status_code == 200                              # account endpoints still work


def test_change_password_unlocks_and_signs_out_other_devices(staff_client):
    new_staff(staff_client)
    laptop, phone = login_as("somchai", "Temp-pass-4821"), login_as("somchai", "Temp-pass-4821")
    r = laptop.post("/api/auth/change-password", {"current_password": "Temp-pass-4821", "new_password": "Better-pass-9137"}, content_type=JSON)
    assert r.status_code == 200 and r.json()["must_change_password"] is False
    assert laptop.get("/api/admin/orders").status_code == 200                    # this browser stays signed in
    assert phone.get("/api/auth/me").status_code == 401                          # the other one is signed out
    assert Client().post("/api/auth/login", {"username": "somchai", "password": "Temp-pass-4821"}, content_type=JSON).status_code == 401
    assert AuditLog.objects.filter(action="password.change", actor="somchai").exists()


@pytest.mark.parametrize("new, why", [
    ("short1A", "too short"), ("1234567890", "all digits"), ("password123", "common"), ("Temp-pass-4821", "same as current"),
])
def test_change_password_rules(staff_client, new, why):
    new_staff(staff_client)
    c = login_as("somchai", "Temp-pass-4821")
    assert c.post("/api/auth/change-password", {"current_password": "Temp-pass-4821", "new_password": new}, content_type=JSON).status_code == 422, why


def test_change_password_needs_the_current_one(staff_client):
    new_staff(staff_client)
    c = login_as("somchai", "Temp-pass-4821")
    assert c.post("/api/auth/change-password", {"current_password": "wrong", "new_password": "Better-pass-9137"}, content_type=JSON).status_code == 400


@pytest.mark.parametrize("over, code", [
    ({"username": "ab"}, 422), ({"username": "Bad Name"}, 422), ({"role": "god"}, 422), ({"password": "weak"}, 422),
    ({"username": "owner"}, 409), ({"username": "OWNER"}, 409),
])
def test_create_staff_validation(staff_client, over, code):
    assert new_staff(staff_client, **over).status_code == code


def test_only_owner_manages_staff(as_role):
    for role in ("manager", "sales", "warehouse", "content"):
        c = as_role(role)
        assert c.get("/api/admin/staff").status_code == 403
        assert new_staff(c).status_code == 403
        assert c.get("/api/admin/audit").status_code == 403


def test_change_role_and_the_new_permissions_apply_immediately(staff_client):
    uid = new_staff(staff_client).json()["id"]
    c = login_as("somchai", "Temp-pass-4821")
    c.post("/api/auth/change-password", {"current_password": "Temp-pass-4821", "new_password": "Better-pass-9137"}, content_type=JSON)
    assert c.get("/api/admin/staff").status_code == 403
    staff_client.put(f"/api/admin/staff/{uid}", {"role": "owner", "is_active": True, "display_name": "สมชาย"}, content_type=JSON)
    assert c.get("/api/admin/staff").status_code == 200                          # same session, new role, no re-login
    log = AuditLog.objects.get(action="staff.update")
    assert "พนักงานขาย → เจ้าของร้าน" in log.detail


def test_disabling_an_account_kicks_the_person_out_at_once(staff_client):
    uid = new_staff(staff_client).json()["id"]
    c = login_as("somchai", "Temp-pass-4821")
    c.post("/api/auth/change-password", {"current_password": "Temp-pass-4821", "new_password": "Better-pass-9137"}, content_type=JSON)
    assert c.get("/api/admin/orders").status_code == 200
    staff_client.put(f"/api/admin/staff/{uid}", {"role": "sales", "is_active": False, "display_name": ""}, content_type=JSON)
    assert c.get("/api/admin/orders").status_code == 401
    assert Client().post("/api/auth/login", {"username": "somchai", "password": "Better-pass-9137"}, content_type=JSON).status_code == 401


def test_reset_password_signs_the_person_out_and_forces_a_change(staff_client):
    uid = new_staff(staff_client).json()["id"]
    c = login_as("somchai", "Temp-pass-4821")
    c.post("/api/auth/change-password", {"current_password": "Temp-pass-4821", "new_password": "Better-pass-9137"}, content_type=JSON)
    r = staff_client.post(f"/api/admin/staff/{uid}/reset-password", {"password": "Reset-pass-5520"}, content_type=JSON)
    assert r.status_code == 200 and r.json()["must_change_password"] is True
    assert c.get("/api/auth/me").status_code == 401
    assert login_as("somchai", "Reset-pass-5520").get("/api/admin/orders").status_code == 403    # must change first
    assert staff_client.post(f"/api/admin/staff/{uid}/reset-password", {"password": "weak"}, content_type=JSON).status_code == 422


def test_owner_cannot_lock_themselves_out_or_remove_the_last_owner(staff_client):
    me = next(s for s in staff_client.get("/api/admin/staff").json() if s["username"] == "owner")
    put = lambda body, uid=me["id"]: staff_client.put(f"/api/admin/staff/{uid}", {"display_name": "", **body}, content_type=JSON)
    assert put({"role": "manager", "is_active": True}).status_code == 409                # demote self
    assert put({"role": "owner", "is_active": False}).status_code == 409                 # disable self
    assert staff_client.post(f"/api/admin/staff/{me['id']}/reset-password", {"password": "Another-pass-77"}, content_type=JSON).status_code == 409
    # a second owner may demote the first, but never the last remaining one
    second = new_staff(staff_client, username="second", role="owner").json()
    c2 = login_as("second", "Temp-pass-4821")
    c2.post("/api/auth/change-password", {"current_password": "Temp-pass-4821", "new_password": "Better-pass-9137"}, content_type=JSON)
    assert c2.put(f"/api/admin/staff/{me['id']}", '{"role":"manager","is_active":true,"display_name":""}', content_type=JSON).status_code == 200
    only = StaffProfile.objects.filter(role="owner", user__is_active=True).count()
    assert only == 1 and second["role"] == "owner"


def test_audit_trail_records_staff_changes_with_who_and_where(staff_client):
    new_staff(staff_client)
    rows = staff_client.get("/api/admin/audit").json()
    assert rows[0]["action"] == "staff.create" and rows[0]["actor"] == "owner" and rows[0]["target"] == "somchai" and rows[0]["ip"]
    assert staff_client.get("/api/admin/audit", {"action": "price"}).json() == []
    assert permissions_of(StaffProfile.objects.get(user__username="somchai").user) == ROLES["sales"]["permissions"]


def test_roles_endpoint_describes_every_role_for_the_ui(staff_client):
    r = staff_client.get("/api/admin/roles").json()
    assert [x["key"] for x in r["roles"]] == list(ROLES) and len(r["permissions"]) == len(PERMISSIONS)


@pytest.mark.parametrize("pw, expected", [
    ("short1A", "สั้นเกินไป"), ("1234567890", "ตัวเลขล้วน"), ("password123", "คาดเดาง่าย"),
])
def test_password_errors_are_in_thai(staff_client, pw, expected):
    r = new_staff(staff_client, password=pw)
    assert r.status_code == 422 and expected in r.json()["detail"]
