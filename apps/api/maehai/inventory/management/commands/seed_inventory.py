from django.core.management.base import BaseCommand

from maehai.inventory.models import Branch
from maehai.shipping.models import ShippingMethod

# (code, name, kind): สาขาศรีณรงค์ is the central warehouse; it receives goods and supplies the other two by transfer slip.
BRANCHES = [("srinarong", "สาขาศรีณรงค์", Branch.Kind.CENTRAL), ("changsanit", "สาขาแจ้งสนิท", Branch.Kind.STORE),
            ("bungwai", "สาขาบุ่งหวาย", Branch.Kind.STORE)]
PICKUP = {"pickup-srinarong": "srinarong", "pickup-changsanit": "changsanit", "pickup-bungwai": "bungwai"}


class Command(BaseCommand):
    help = "Create the shop branches (the central warehouse and the stores and link each pickup method to its branch. No stock is invented: enter counts in the back office."

    def handle(self, *args, **opts):
        for i, (code, name, kind) in enumerate(BRANCHES):
            Branch.objects.update_or_create(code=code, defaults={"name": name, "kind": kind, "sort_order": i})
        for method, branch in PICKUP.items():
            ShippingMethod.objects.filter(code=method).update(branch=Branch.objects.get(code=branch))
        self.stdout.write(self.style.SUCCESS(f"Branches: {Branch.objects.count()}."))
