"""A tiny scheduler for the Docker deployment, so no cron or extra tooling is needed.

Runs the periodic jobs on a fixed interval until stopped. Each job runs in its own try/except:
one failure is logged and retried next round, it never stops the loop.
"""
import logging
import time

from django.core.management import call_command
from django.core.management.base import BaseCommand

log = logging.getLogger(__name__)

# (management command, minutes between runs)
JOBS = [("expire_unpaid_orders", 60)]


class Command(BaseCommand):
    help = "Run periodic jobs (expire unpaid orders hourly). Use --once to run every job a single time and exit."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true")

    def handle(self, *args, once, **opts):
        next_run = {name: 0.0 for name, _ in JOBS}
        while True:
            now = time.monotonic()
            for name, minutes in JOBS:
                if once or now >= next_run[name]:
                    try:
                        call_command(name)
                    except Exception:
                        log.exception("scheduled job %s failed", name)
                    next_run[name] = now + minutes * 60
            if once:
                return
            time.sleep(30)
