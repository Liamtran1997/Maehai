from django.conf import settings
from django.db import models


class StaffProfile(models.Model):
    """Role and onboarding state of a back-office user. See permissions.py for what each role may do."""

    ROLE_CHOICES = [("owner", "เจ้าของร้าน"), ("manager", "ผู้จัดการ"), ("branch_manager", "ผู้จัดการสาขา"),
                    ("sales", "พนักงานขาย"), ("warehouse", "พนักงานคลัง"), ("content", "พนักงานดูแลสินค้า")]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="staff_profile")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    display_name = models.CharField(max_length=80, blank=True)
    must_change_password = models.BooleanField(default=False, help_text="Set when an owner creates the account or resets the password")
    created_by = models.CharField(max_length=150, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    branches = models.ManyToManyField("inventory.Branch", blank=True, related_name="staff",
                                      help_text="Branches this person works with. ผู้จัดการสาขา: exactly one")

    def __str__(self) -> str:
        return f"{self.user.get_username()} ({self.role})"


class AuditLog(models.Model):
    """Who did a sensitive thing, and what. Append-only: nothing in the app edits or deletes these rows."""

    actor = models.CharField(max_length=150)
    action = models.CharField(max_length=40, db_index=True)
    target = models.CharField(max_length=150, blank=True)
    detail = models.CharField(max_length=500, blank=True)
    ip = models.CharField(max_length=45, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]


def audit(request, action: str, target: str = "", detail: str = "") -> None:
    from .ratelimit import client_ip

    AuditLog.objects.create(actor=request.user.get_username(), action=action, target=target[:150], detail=detail[:500], ip=client_ip(request))
