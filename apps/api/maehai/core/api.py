from django.contrib.auth import authenticate, login, logout
from django.middleware.csrf import get_token
from ninja import Router, Schema

from . import ratelimit
from .auth import staff_auth

router = Router(tags=["auth"])


class LoginIn(Schema):
    username: str
    password: str


class MeOut(Schema):
    username: str
    is_staff: bool


@router.post("/login", response={200: MeOut, 401: dict})
def login_view(request, data: LoginIn):
    ip, name = ratelimit.client_ip(request), data.username.strip().lower()
    ratelimit.blocked("login_fail_ip", ip)
    ratelimit.blocked("login_fail_user", name)
    user = authenticate(request, username=data.username, password=data.password)
    if user is None or not user.is_staff:
        ratelimit.failed("login_fail_ip", ip)
        ratelimit.failed("login_fail_user", name)
        return 401, {"detail": "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง"}
    ratelimit.forgive("login_fail_user", name)
    login(request, user)
    return 200, {"username": user.get_username(), "is_staff": user.is_staff}


@router.post("/logout", auth=staff_auth)
def logout_view(request):
    logout(request)
    return {"ok": True}


@router.get("/me", auth=staff_auth, response=MeOut)
def me(request):
    return {"username": request.user.get_username(), "is_staff": request.user.is_staff}


@router.get("/csrf")
def csrf(request):
    """Sets the csrftoken cookie. The admin app sends its value back in the X-CSRFToken header on every write."""
    return {"csrf_token": get_token(request)}
