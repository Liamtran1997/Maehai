from ninja.errors import HttpError

from maehai.core import ratelimit

from . import services
from .models import Order


def order_by_token(request, number: str, token: str) -> Order:
    """Find an order from its secret link. Repeated wrong tokens from one IP are blocked: the token is long enough
    that guessing is hopeless, this just stops it being tried at all."""
    ip = ratelimit.client_ip(request)
    ratelimit.blocked("token_fail_ip", ip)
    try:
        return services.find_by_token(number, token)
    except HttpError as e:
        if e.status_code == 404:
            ratelimit.failed("token_fail_ip", ip)
        raise
