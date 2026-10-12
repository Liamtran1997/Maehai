from django.contrib import admin

from .models import Coupon, CouponRedemption


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "kind", "value", "is_active", "starts_at", "ends_at")
    search_fields = ("code", "name")


@admin.register(CouponRedemption)
class CouponRedemptionAdmin(admin.ModelAdmin):
    list_display = ("coupon", "order", "phone", "discount_satang", "created_at", "released_at")
    readonly_fields = [f.name for f in CouponRedemption._meta.fields]
