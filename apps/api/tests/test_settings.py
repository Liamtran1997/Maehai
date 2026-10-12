import os
import subprocess
import sys
from pathlib import Path

API_DIR = Path(__file__).resolve().parent.parent


def load_settings(**env):
    base = {k: v for k, v in os.environ.items() if not k.startswith(("DJANGO_", "DATABASE_URL", "REDIS_URL"))}
    return subprocess.run([sys.executable, "-c", "import config.settings as s; print(s.DEBUG, s.SESSION_COOKIE_SECURE if not s.DEBUG else '-')"],
                          cwd=API_DIR, env={**base, **env}, capture_output=True, text=True)


def test_production_refuses_to_start_without_a_real_secret():
    r = load_settings(DJANGO_DEBUG="0")
    assert r.returncode != 0 and "DJANGO_SECRET_KEY" in r.stderr
    assert load_settings(DJANGO_DEBUG="0", DJANGO_SECRET_KEY="short").returncode != 0
    assert load_settings(DJANGO_DEBUG="0", DJANGO_SECRET_KEY="dev-only-" + "x" * 40).returncode != 0


def test_production_turns_on_secure_cookies():
    r = load_settings(DJANGO_DEBUG="0", DJANGO_SECRET_KEY="k" * 50)
    assert r.returncode == 0 and r.stdout.split() == ["False", "True"]


def test_development_needs_no_secret():
    assert load_settings(DJANGO_DEBUG="1").returncode == 0
