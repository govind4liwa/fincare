"""Read-only admin for the audit trail."""

from django.contrib import admin

from apps.audit.models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "action", "actor", "content_type", "object_repr", "entity_id")
    list_filter = ("action", "content_type", "timestamp")
    search_fields = ("object_repr", "object_id", "message")
    date_hierarchy = "timestamp"
    readonly_fields = (
        "timestamp",
        "actor",
        "action",
        "content_type",
        "object_id",
        "object_repr",
        "entity_id",
        "changes",
        "message",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
