from django.core.management.base import BaseCommand

from maehai.inventory.models import Branch
from maehai.shipping.models import ShippingMethod

BRANCHES = [("srinarong", "สาขาศรีณรงค์"), ("changsanit", "สาขาแจ้งสนิท")]
PICKUP = {"pickup-srinarong": "srinarong", "pickup-changsanit": "changsanit"}


class Command(BaseCommand):
    help = "Create the two shop branches and link each pickup method to its branch. No stock is invented: enter counts in the back office."

    def handle(self, *args, **opts):
        for i, (code, name) in enumerate(BRANCHES):
            Branch.objects.update_or_create(code=code, defaults={"name": name, "sort_order": i})
        for method, branch in PICKUP.items():
            ShippingMethod.objects.filter(code=method).update(branch=Branch.objects.get(code=branch))
        self.stdout.write(self.style.SUCCESS(f"Branches: {Branch.objects.count()}."))
