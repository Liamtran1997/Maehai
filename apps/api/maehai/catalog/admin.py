from django.contrib import admin

from .models import Category, Product, ProductVariant


class VariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "is_active", "sort_order")
    list_filter = ("category", "is_active")
    search_fields = ("name", "name_en", "slug")
    prepopulated_fields = {"slug": ("name_en",)}
    inlines = [VariantInline]


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "sort_order")
