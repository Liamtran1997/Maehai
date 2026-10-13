"""Who may do what in the back office.

Roles are fixed in code (not editable in the database) so the rules are reviewable, testable and cannot be
loosened by mistake. Every admin endpoint names the permission it needs; the server enforces it. The admin app only
hides buttons for tidiness.
"""
from ninja.errors import HttpError
from ninja.security import SessionAuth

# permission -> what it lets a person do (shown in the staff screen)
PERMISSIONS: dict[str, str] = {
    "reports.view": "ดูยอดขายและรายงาน",
    "orders.view": "ดูคำสั่งซื้อ ข้อมูลลูกค้า และที่อยู่จัดส่ง",
    "orders.quote": "แจ้งค่าจัดส่ง",
    "orders.fulfil": "จัดเตรียม ส่ง และปิดคำสั่งซื้อ เปลี่ยนสาขาที่จัดสินค้า",
    "orders.cancel": "ยกเลิกคำสั่งซื้อที่ยังไม่ชำระเงิน",
    "orders.cancel_paid": "ยกเลิกคำสั่งซื้อที่ชำระเงินแล้ว (ต้องคืนเงินเอง)",
    "payments.review": "ดูสลิปโอนเงิน ยืนยันหรือปฏิเสธการชำระเงิน",
    "catalog.view": "ดูสินค้า หมวดหมู่ และโปรโมชัน",
    "coupons.view": "ดูรายการโค้ดส่วนลดและประวัติการใช้ (โค้ดคือเงิน จึงแยกจากสิทธิ์ดูสินค้า)",
    "catalog.edit": "เพิ่มและแก้ไขสินค้า รูปภาพ และหมวดหมู่",
    "pricing.manage": "แก้ราคา สร้างโปรโมชันและโค้ดส่วนลด",
    "inventory.view": "ดูสต็อกสินค้าและเอกสารคลังของสาขาที่ได้รับมอบหมาย",
    "inventory.adjust": "ตัดของเสีย เบิกใช้ นับสต็อก หมดหน้าร้าน ตั้งโควตาออนไลน์ และสร้างใบคืนจากสาขา",
    "inventory.receive": "รับของจากแหล่งสินค้าเข้าคลังกลาง จัดการแหล่งสินค้าและรายการวัตถุดิบ",
    "inventory.transfer": "สร้างและยกเลิกใบส่งสินค้าจากคลังกลางไปสาขา",
    "inventory.receive_transfer": "ตรวจรับสินค้าที่ส่งมาถึงสาขาของตัวเอง",
    "inventory.receive_return": "รับใบคืนสินค้าเข้าคลังกลาง และตัดสินใจเข้าสต็อกหรือทิ้ง",
    "inventory.approve": "ยืนยันรับแทนสาขา และดูรายงานคลังทั้งหมด",
    "staff.manage": "จัดการพนักงาน กำหนดสิทธิ์ และดูประวัติการใช้งาน",
}

# Roles that see every branch. Everyone else sees only the branches assigned to them.
ALL_BRANCH_ROLES = {"owner", "manager"}

ROLES: dict[str, dict] = {
    "owner": {
        "label": "เจ้าของร้าน",
        "description": "ทำได้ทุกอย่าง รวมถึงจัดการพนักงาน",
        "permissions": set(PERMISSIONS),
    },
    "manager": {
        "label": "ผู้จัดการ",
        "description": "ทำได้ทุกอย่างยกเว้นจัดการพนักงาน",
        "permissions": set(PERMISSIONS) - {"staff.manage"},
    },
    "sales": {
        "label": "พนักงานขาย",
        "description": "รับออเดอร์ แจ้งค่าส่ง ตรวจสลิป และจัดส่ง ดูสินค้าได้แต่แก้ไม่ได้",
        "permissions": {"orders.view", "orders.quote", "orders.fulfil", "orders.cancel", "payments.review",
                        "catalog.view", "coupons.view", "inventory.view"},
    },
    "warehouse": {
        "label": "พนักงานคลัง",
        "description": "จัดเตรียมและส่งสินค้า จัดการสต็อกและใบส่งของ มองไม่เห็นเงินและสลิป",
        "permissions": {"orders.view", "orders.fulfil", "catalog.view", "inventory.view", "inventory.adjust",
                        "inventory.transfer", "inventory.receive_return"},
    },
    "branch_manager": {
        "label": "ผู้จัดการสาขา",
        "description": "ดูแลสาขาที่ได้รับมอบหมาย จัดส่งและรับสินค้าเข้าสาขา มองไม่เห็นเงินและสลิป",
        "permissions": {"orders.view", "orders.fulfil", "catalog.view", "inventory.view", "inventory.adjust",
                        "inventory.receive_transfer"},
    },
    "content": {
        "label": "พนักงานดูแลสินค้า",
        "description": "เพิ่มและแก้ไขสินค้า รูปภาพ หมวดหมู่ แต่แก้ราคาและทำโปรโมชันไม่ได้",
        "permissions": {"catalog.view", "catalog.edit", "inventory.view"},
    },
}


def role_of(user) -> str | None:
    """A user's role. Superusers made with `createsuperuser` count as owner. Staff with no profile get nothing."""
    if not (user and user.is_authenticated and user.is_active):
        return None
    profile = getattr(user, "staff_profile", None)
    if profile is not None:
        return profile.role
    return "owner" if user.is_superuser else None


def visible_branch_ids(user) -> set[int] | None:
    """Branches this person may see and act on. None = every branch."""
    role = role_of(user)
    if role in ALL_BRANCH_ROLES:
        return None
    profile = getattr(user, "staff_profile", None)
    if profile is None:
        return set()
    return set(profile.branches.values_list("id", flat=True))


def permissions_of(user) -> set[str]:
    role = role_of(user)
    return set(ROLES[role]["permissions"]) if role in ROLES else set()


def has(user, perm: str) -> bool:
    return perm in permissions_of(user)


def check(request, perm: str) -> None:
    """For rules that depend on the request body (for example: cancelling a paid order). Raises 403."""
    if not has(request.user, perm):
        raise HttpError(403, "คุณไม่มีสิทธิ์ทำรายการนี้")


class PermissionAuth(SessionAuth):
    """Session cookie + CSRF, and the logged-in person must hold `perm` (None = any active staff member).
    A person who must change their password is blocked everywhere except the account endpoints."""

    def __init__(self, perm: str | None, *, allow_password_change_pending: bool = False):
        super().__init__(csrf=True)
        self.perm = perm
        self.allow_pending = allow_password_change_pending

    def authenticate(self, request, key):
        user = getattr(request, "user", None)
        if role_of(user) is None or not user.is_staff:
            return None                                              # 401: not logged in as staff
        profile = getattr(user, "staff_profile", None)
        if profile is not None and profile.must_change_password and not self.allow_pending:
            raise HttpError(403, "ต้องเปลี่ยนรหัสผ่านก่อนใช้งาน")
        if self.perm is not None and self.perm not in permissions_of(user):
            raise HttpError(403, "คุณไม่มีสิทธิ์ทำรายการนี้")           # 403: logged in but not allowed
        return user


def requires(perm: str | None) -> PermissionAuth:
    return PermissionAuth(perm)


# For the account endpoints (me, logout, change password): any active staff member, even before changing a temporary password.
account_auth = PermissionAuth(None, allow_password_change_pending=True)
