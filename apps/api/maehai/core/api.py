from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.middleware.csrf import get_token
from ninja import Router, Schema

from . import ratelimit
from .auth import account_auth
from .models import audit
from .permissions import ROLES, permissions_of, role_of

router = Router(tags=["auth"])


class LoginIn(Schema):
    username: str
    password: str


class MeOut(Schema):
    username: str
    display_name: str
    role: str
    role_label: str
    permissions: list[str]
    must_change_password: bool


class PasswordIn(Schema):
    current_password: str
    new_password: str


def me_out(user) -> dict:
    role = role_of(user)
    profile = getattr(user, "staff_profile", None)
    return {"username": user.get_username(), "display_name": (profile.display_name if profile else "") or user.get_username(),
            "role": role, "role_label": ROLES[role]["label"], "permissions": sorted(permissions_of(user)),
            "must_change_password": bool(profile and profile.must_change_password)}


THAI_PASSWORD_MESSAGES = {
    "password_too_short": "รหัสผ่านสั้นเกินไป ต้องมีอย่างน้อย 10 ตัวอักษร",
    "password_too_common": "รหัสผ่านนี้เป็นรหัสที่คนใช้กันมาก คาดเดาง่าย",
    "password_entirely_numeric": "รหัสผ่านเป็นตัวเลขล้วนไม่ได้",
    "password_too_similar": "รหัสผ่านคล้ายชื่อผู้ใช้เกินไป",
}


def password_errors(user, password: str) -> list[str]:
    """Why a password is refused, in Thai. Empty list = acceptable."""
    try:
        validate_password(password, user)
        return []
    except ValidationError as e:
        return [THAI_PASSWORD_MESSAGES.get(err.code, "รหัสผ่านนี้ไม่ปลอดภัยพอ") for err in e.error_list]


@router.post("/login", response={200: MeOut, 401: dict})
def login_view(request, data: LoginIn):
    ip, name = ratelimit.client_ip(request), data.username.strip().lower()
    ratelimit.blocked("login_fail_ip", ip)
    ratelimit.blocked("login_fail_user", name)
    user = authenticate(request, username=data.username, password=data.password)
    # A valid password is not enough: the account must be an active staff member with a role.
    if user is None or not user.is_staff or role_of(user) is None:
        ratelimit.failed("login_fail_ip", ip)
        ratelimit.failed("login_fail_user", name)
        return 401, {"detail": "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง"}
    ratelimit.forgive("login_fail_user", name)
    login(request, user)
    return 200, me_out(user)


@router.post("/logout", auth=account_auth)
def logout_view(request):
    logout(request)
    return {"ok": True}


@router.get("/me", auth=account_auth, response=MeOut)
def me(request):
    return me_out(request.user)


@router.post("/change-password", auth=account_auth, response={200: MeOut, 400: dict, 422: dict})
def change_password(request, data: PasswordIn):
    user = request.user
    name = user.get_username().lower()
    ratelimit.blocked("login_fail_user", name)                  # guessing the current password is throttled like logging in
    if not user.check_password(data.current_password):
        ratelimit.failed("login_fail_user", name)
        return 400, {"detail": "รหัสผ่านปัจจุบันไม่ถูกต้อง"}
    if data.new_password == data.current_password:
        return 422, {"detail": "รหัสผ่านใหม่ต้องไม่ซ้ำรหัสเดิม"}
    errors = password_errors(user, data.new_password)
    if errors:
        return 422, {"detail": " ".join(errors)}
    user.set_password(data.new_password)
    user.save(update_fields=["password"])
    update_session_auth_hash(request, user)                     # keep this browser logged in; every other session is signed out
    if getattr(user, "staff_profile", None):
        user.staff_profile.must_change_password = False
        user.staff_profile.save(update_fields=["must_change_password"])
    audit(request, "password.change", user.get_username())
    return 200, me_out(user)


@router.get("/csrf")
def csrf(request):
    """Sets the csrftoken cookie. The admin app sends its value back in the X-CSRFToken header on every write."""
    return {"csrf_token": get_token(request)}
