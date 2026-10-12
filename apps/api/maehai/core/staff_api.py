"""Owner-only staff management and the audit trail."""
import re

from django.contrib.auth import get_user_model
from django.db import transaction
from django.shortcuts import get_object_or_404
from ninja import Field, Router, Schema
from ninja.errors import HttpError

from .api import password_errors
from .auth import requires
from .models import AuditLog, StaffProfile, audit
from .permissions import PERMISSIONS, ROLES

User = get_user_model()
router = Router(tags=["admin-staff"])
MANAGE = requires("staff.manage")

USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,29}$")


class StaffOut(Schema):
    id: int
    username: str
    display_name: str
    role: str
    role_label: str
    is_active: bool
    must_change_password: bool
    last_login: str | None
    created_at: str


class StaffIn(Schema):
    username: str
    display_name: str = Field(default="", max_length=80)
    role: str
    password: str


class StaffUpdate(Schema):
    display_name: str = Field(default="", max_length=80)
    role: str
    is_active: bool


class ResetIn(Schema):
    password: str


class RoleOut(Schema):
    key: str
    label: str
    description: str
    permissions: list[str]


class PermissionOut(Schema):
    key: str
    label: str


class RolesOut(Schema):
    roles: list[RoleOut]
    permissions: list[PermissionOut]


class AuditOut(Schema):
    created_at: str
    actor: str
    action: str
    target: str
    detail: str
    ip: str


def _out(p: StaffProfile) -> dict:
    u = p.user
    return {"id": u.id, "username": u.get_username(), "display_name": p.display_name, "role": p.role,
            "role_label": ROLES[p.role]["label"], "is_active": u.is_active, "must_change_password": p.must_change_password,
            "last_login": u.last_login.isoformat() if u.last_login else None, "created_at": p.created_at.isoformat()}


def _ensure_superuser_profiles() -> None:
    """A superuser made with `createsuperuser` is an owner (see role_of) but has no profile yet.
    Give each one a profile, so the staff list and the last-owner guard both see them."""
    for u in get_user_model().objects.filter(is_superuser=True, staff_profile__isnull=True):
        StaffProfile.objects.create(user=u, role="owner", display_name=u.get_username(), created_by="createsuperuser")


def _active_owners() -> int:
    _ensure_superuser_profiles()
    return StaffProfile.objects.filter(role="owner", user__is_active=True).count()


@router.get("/roles", auth=MANAGE, response=RolesOut)
def roles(request):
    return {"roles": [{"key": k, "label": v["label"], "description": v["description"], "permissions": sorted(v["permissions"])} for k, v in ROLES.items()],
            "permissions": [{"key": k, "label": v} for k, v in PERMISSIONS.items()]}


@router.get("/staff", auth=MANAGE, response=list[StaffOut])
def list_staff(request):
    _ensure_superuser_profiles()
    return [_out(p) for p in StaffProfile.objects.select_related("user").order_by("user__username")]


@router.post("/staff", auth=MANAGE, response={201: StaffOut})
@transaction.atomic
def create_staff(request, data: StaffIn):
    username = data.username.strip().lower()
    if not USERNAME_RE.match(username):
        raise HttpError(422, "ชื่อผู้ใช้ใช้ a-z ตัวเลข จุด ขีดกลาง หรือขีดล่าง ยาว 3 ถึง 30 ตัว")
    if data.role not in ROLES:
        raise HttpError(422, "ตำแหน่งไม่ถูกต้อง")
    if User.objects.filter(username__iexact=username).exists():
        raise HttpError(409, "ชื่อผู้ใช้นี้มีอยู่แล้ว")
    user = User(username=username, is_staff=True)
    errors = password_errors(user, data.password)
    if errors:
        raise HttpError(422, " ".join(errors))
    user.set_password(data.password)
    user.save()
    p = StaffProfile.objects.create(user=user, role=data.role, display_name=data.display_name.strip(),
                                    must_change_password=True, created_by=request.user.get_username())
    audit(request, "staff.create", username, f"ตำแหน่ง {ROLES[data.role]['label']}")
    return 201, _out(p)


@router.put("/staff/{user_id}", auth=MANAGE, response=StaffOut)
@transaction.atomic
def update_staff(request, user_id: int, data: StaffUpdate):
    p = get_object_or_404(StaffProfile.objects.select_related("user"), user_id=user_id)
    if data.role not in ROLES:
        raise HttpError(422, "ตำแหน่งไม่ถูกต้อง")
    if p.user_id == request.user.id and (data.role != p.role or not data.is_active):
        raise HttpError(409, "เปลี่ยนตำแหน่งหรือปิดบัญชีของตัวเองไม่ได้ ให้เจ้าของร้านคนอื่นทำแทน")
    leaving_owner = p.role == "owner" and p.user.is_active and (data.role != "owner" or not data.is_active)
    if leaving_owner and _active_owners() <= 1:
        raise HttpError(409, "ต้องมีเจ้าของร้านที่ใช้งานอยู่อย่างน้อย 1 คน")
    changes = []
    if data.role != p.role:
        changes.append(f"ตำแหน่ง {ROLES[p.role]['label']} → {ROLES[data.role]['label']}")
    if data.is_active != p.user.is_active:
        changes.append("เปิดบัญชี" if data.is_active else "ปิดบัญชี")
    p.role, p.display_name = data.role, data.display_name.strip()
    p.save()
    p.user.is_active = data.is_active
    p.user.save(update_fields=["is_active"])
    if changes:
        audit(request, "staff.update", p.user.get_username(), "; ".join(changes))
    return _out(p)


@router.post("/staff/{user_id}/reset-password", auth=MANAGE, response=StaffOut)
@transaction.atomic
def reset_password(request, user_id: int, data: ResetIn):
    p = get_object_or_404(StaffProfile.objects.select_related("user"), user_id=user_id)
    if p.user_id == request.user.id:
        raise HttpError(409, "รหัสผ่านของตัวเองให้ใช้เมนู “เปลี่ยนรหัสผ่าน”")
    errors = password_errors(p.user, data.password)
    if errors:
        raise HttpError(422, " ".join(errors))
    p.user.set_password(data.password)           # changing the hash signs this person out of every device
    p.user.save(update_fields=["password"])
    p.must_change_password = True
    p.save(update_fields=["must_change_password"])
    audit(request, "staff.reset_password", p.user.get_username())
    return _out(p)


@router.get("/audit", auth=MANAGE, response=list[AuditOut])
def audit_log(request, action: str | None = None, limit: int = 100):
    qs = AuditLog.objects.all()
    if action:
        qs = qs.filter(action__startswith=action)
    return [{"created_at": a.created_at.isoformat(), "actor": a.actor, "action": a.action, "target": a.target, "detail": a.detail, "ip": a.ip}
            for a in qs[: max(1, min(limit, 500))]]
