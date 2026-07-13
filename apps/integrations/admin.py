"""Admin for the Integrations module."""

from django.contrib import admin

from apps.integrations.models import ImportBatch, ImportProfile


@admin.register(ImportProfile)
class ImportProfileAdmin(admin.ModelAdmin):
    list_display = ("kind", "source_key", "name", "entity", "is_active")
    list_filter = ("kind", "is_active")
    search_fields = ("source_key", "name")


@admin.register(ImportBatch)
class ImportBatchAdmin(admin.ModelAdmin):
    list_display = (
        "kind",
        "filename",
        "entity",
        "created_count",
        "skipped_count",
        "status",
        "imported_at",
    )
    list_filter = ("kind", "status", "entity")
    date_hierarchy = "created_at"
    readonly_fields = ("file_hash", "imported_at", "imported_by")
