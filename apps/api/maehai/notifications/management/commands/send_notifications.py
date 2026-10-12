import time

from django.core.management.base import BaseCommand

from maehai.notifications.delivery import deliver_pending


class Command(BaseCommand):
    help = "Send queued LINE messages. Run with --loop as a long-lived worker, or from cron once a minute."

    def add_arguments(self, parser):
        parser.add_argument("--loop", action="store_true")
        parser.add_argument("--interval", type=int, default=5, help="Seconds between polls with --loop")

    def handle(self, *args, loop, interval, **opts):
        while True:
            counts = deliver_pending()
            if any(counts.values()):
                self.stdout.write(str(counts))
            if not loop:
                return
            time.sleep(interval)
