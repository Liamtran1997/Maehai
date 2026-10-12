from django.contrib import admin

from .models import Outbox


@admin.register(Outbox)
class OutboxAdmin(admin.ModelAdmin):
    list_display = ("id", "created_at", "audience", "kind", "status", "attempts", "last_error")
    list_filter = ("status", "audience", "kind")
    readonly_fields = [f.name for f in Outbox._meta.fields]
