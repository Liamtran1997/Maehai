from django.contrib import admin, messages

from . import services
from .models import Payment, PaymentStatus


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "amount_satang", "status", "slip_submitted_at", "decided_by")
    list_filter = ("status",)
    readonly_fields = ("order", "amount_satang", "qr_payload", "expires_at", "slip_submitted_at", "confirmed_at", "decided_by")
    actions = ["confirm_selected"]

    @admin.action(description="ยืนยันการชำระเงิน (ตรวจสลิปแล้ว)")
    def confirm_selected(self, request, queryset):
        for p in queryset.filter(status=PaymentStatus.SLIP_SUBMITTED):
            services.confirm(p, actor=request.user.get_username())
        self.message_user(request, "ยืนยันแล้ว", messages.SUCCESS)
