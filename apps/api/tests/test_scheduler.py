from io import StringIO

import pytest
from django.core.management import call_command

pytestmark = pytest.mark.django_db


def test_once_runs_every_job_and_exits(seeded):
    out = StringIO()
    call_command("run_scheduler", "--once", stdout=out)   # would hang if --once were ignored


def test_a_failing_job_does_not_stop_the_scheduler(monkeypatch):
    from maehai.core.management.commands import run_scheduler

    calls = []

    def boom(name, *a, **k):
        calls.append(name)
        raise RuntimeError("db down")

    monkeypatch.setattr(run_scheduler, "call_command", boom)
    call_command("run_scheduler", "--once")
    assert calls == ["expire_unpaid_orders", "alert_overdue_slips"]
