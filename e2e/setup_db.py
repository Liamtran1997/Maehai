# Run by global-setup through `manage.py shell` against the e2e database only.
from django.contrib.auth import get_user_model

from maehai.core.models import StaffProfile

User = get_user_model()


def make(username, role, password, must_change=False):
    User.objects.filter(username=username).delete()
    u = User.objects.create_user(username, password=password, is_staff=True)
    StaffProfile.objects.create(user=u, role=role, must_change_password=must_change, display_name=username)


make("owner", "owner", "E2e-owner-pass-1")
make("kho", "warehouse", "E2e-kho-pass-22")
make("newstaff", "sales", "Temp-e2e-pass-3", must_change=True)
print("e2e accounts ready")
