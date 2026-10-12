from django.contrib import admin

from .models import Order, OrderEvent, OrderItem


class ItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False
    readonly_fields = ("sku", "product_name", "variant_label", "unit_price_satang", "quantity")


class EventInline(admin.TabularInline):
    model = OrderEvent
    extra = 0
    can_delete = False
    readonly_fields = ("created_at", "actor", "kind", "detail")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("number", "customer_name", "phone", "status", "subtotal_satang", "shipping_fee_satang", "created_at")
    list_filter = ("status", "shipping_method")
    search_fields = ("number", "customer_name", "phone")
    readonly_fields = ("number", "public_token", "status", "subtotal_satang", "shipping_fee_satang", "vat_satang")
    inlines = [ItemInline, EventInline]
