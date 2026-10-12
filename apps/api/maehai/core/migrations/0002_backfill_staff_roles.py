from django.db import migrations


def give_existing_staff_a_role(apps, schema_editor):
    """Before roles existed every staff member could do everything. Keep their access: superusers become the owner,
    other staff become managers (everything except managing people). Owners can tighten this afterwards."""
    User = apps.get_model("auth", "User")
    Profile = apps.get_model("core", "StaffProfile")
    for u in User.objects.filter(is_staff=True):
        Profile.objects.get_or_create(user=u, defaults={"role": "owner" if u.is_superuser else "manager", "created_by": "migration"})


class Migration(migrations.Migration):
    dependencies = [("core", "0001_initial"), ("auth", "0012_alter_user_first_name_max_length")]
    operations = [migrations.RunPython(give_existing_staff_a_role, migrations.RunPython.noop)]
