from django.core.management.base import BaseCommand

from maehai.inventory.documents import alert_overdue


class Command(BaseCommand):
    help = "Tell the managers once about transfer and return slips nobody has confirmed for 24 hours. Run hourly."

    def handle(self, *args, **opts):
        n = alert_overdue()
        self.stdout.write(f"Alerted {n} overdue slip(s).")
