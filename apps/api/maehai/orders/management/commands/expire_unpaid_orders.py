from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from maehai.orders import services
from maehai.orders.models import Order, OrderStatus
from maehai.payments.models import PaymentStatus


class Command(BaseCommand):
    help = ("Cancel orders still unpaid after ORDER_UNPAID_EXPIRY_HOURS so their reserved stock goes back on sale. "
            "Orders with a slip waiting for review, and orders still waiting for the shop to quote shipping, are never touched. Run hourly.")

    def add_arguments(self, parser):
        parser.add_argument("--hours", type=int, default=settings.ORDER_UNPAID_EXPIRY_HOURS)

    def handle(self, *args, hours, **opts):
        cutoff = timezone.now() - timedelta(hours=hours)
        stale = (Order.objects.filter(status=OrderStatus.WAITING_PAYMENT, created_at__lt=cutoff)
                 .exclude(payments__status=PaymentStatus.SLIP_SUBMITTED))
        n = 0
        for o in stale:
            services.staff_set_status(o, OrderStatus.CANCELLED, actor="system", tracking_ref=f"หมดเวลาชำระเงิน {hours} ชม.")
            n += 1
        self.stdout.write(f"Cancelled {n} unpaid order(s).")
