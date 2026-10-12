"""Single Ninja API. Each domain app exposes a `router` that is mounted here."""
from ninja import NinjaAPI

from maehai.core.ratelimit import MESSAGE, RateLimited

api = NinjaAPI(title="Maehai API", version="0.1.0")


@api.exception_handler(RateLimited)
def on_rate_limited(request, exc: RateLimited):
    response = api.create_response(request, {"detail": MESSAGE, "retry_after": exc.retry_after}, status=429)
    response["Retry-After"] = str(exc.retry_after)
    return response


@api.get("/health", tags=["system"])
def health(request):
    return {"status": "ok"}


api.add_router("/auth/", "maehai.core.api.router")
api.add_router("/admin/", "maehai.core.staff_api.router")
api.add_router("/catalog/", "maehai.catalog.api.router")
api.add_router("/admin/catalog/", "maehai.catalog.admin_api.router")
api.add_router("/admin/", "maehai.coupons.admin_api.router")
api.add_router("/shipping/", "maehai.shipping.api.router")
api.add_router("/coupons", "maehai.coupons.api.router")
api.add_router("/orders", "maehai.orders.api.router")
api.add_router("/payments/", "maehai.payments.api.router")
api.add_router("/line/", "maehai.notifications.api.router")
api.add_router("/admin/inventory/", "maehai.inventory.api.router")
api.add_router("/admin/", "maehai.orders.admin_api.router")
api.add_router("/admin/reports/", "maehai.reports.api.router")
