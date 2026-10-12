"""Fixed-window rate limits on the Django cache.

Two kinds:
  hit(...)            counts every request and blocks once over the limit (abuse of an endpoint)
  blocked / failed    counts only FAILURES and blocks once too many pile up (guessing codes, passwords, phones)

Counters are one atomic cache increment, so they are safe across threads and, with Redis, across workers.
"""
import hashlib
import time

from django.conf import settings
from django.core.cache import cache


class RateLimited(Exception):
    def __init__(self, retry_after: int):
        super().__init__("rate limited")
        self.retry_after = max(1, int(retry_after))


MESSAGE = "ส่งคำขอถี่เกินไป กรุณารอสักครู่แล้วลองใหม่"


def _now() -> float:  # replaced in tests
    return time.time()


def client_ip(request) -> str:
    """The caller's address. X-Forwarded-For is only believed for the number of proxies we run, counted from the right,
    because a client can put anything it likes at the left end of that header."""
    n = settings.TRUSTED_PROXY_COUNT
    if n > 0:
        parts = [p.strip() for p in request.META.get("HTTP_X_FORWARDED_FOR", "").split(",") if p.strip()]
        if len(parts) >= n:
            return parts[-n]
    return request.META.get("REMOTE_ADDR", "unknown")


def _key(policy: str, ident: str, window: int) -> tuple[str, int]:
    bucket = int(_now() // window)
    digest = hashlib.sha256(str(ident).encode()).hexdigest()[:24]  # keeps odd characters (Thai usernames) out of cache keys
    return f"rl:{policy}:{digest}:{bucket}", window - int(_now() % window)


def _policy(name: str) -> tuple[int, int]:
    return settings.RATE_LIMITS[name]


def hit(policy: str, ident: str) -> None:
    """Count one request. Raises RateLimited once the policy's limit is exceeded."""
    if not settings.RATE_LIMIT_ENABLED:
        return
    limit, window = _policy(policy)
    key, remaining = _key(policy, ident, window)
    cache.add(key, 0, timeout=window)
    if cache.incr(key) > limit:
        raise RateLimited(remaining)


def blocked(policy: str, ident: str) -> None:
    """Raise if this identity has already used up its allowed failures. Does not count anything."""
    if not settings.RATE_LIMIT_ENABLED:
        return
    limit, window = _policy(policy)
    key, remaining = _key(policy, ident, window)
    if (cache.get(key) or 0) >= limit:
        raise RateLimited(remaining)


def failed(policy: str, ident: str) -> None:
    if not settings.RATE_LIMIT_ENABLED:
        return
    _, window = _policy(policy)
    key, _ = _key(policy, ident, window)
    cache.add(key, 0, timeout=window)
    cache.incr(key)


def forgive(policy: str, ident: str) -> None:
    """Forget failures after a success, so a customer who finally types the right phone is not left locked."""
    _, window = _policy(policy)
    cache.delete(_key(policy, ident, window)[0])
