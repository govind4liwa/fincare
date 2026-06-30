"""Admin for the Platforms module."""

from django.contrib import admin

from apps.platforms.models import EarningImport, Platform, PlatformSettlement


@admin.register(Platform)
class PlatformAdmin(admin.ModelAdmin):
    list_display = ("name", "commission_pct", "settlement_cycle", "entity", "is_active")
    list_filter = ("is_active", "entity")
    search_fields = ("name",)


class EarningImportInline(admin.TabularInline):
    model = EarningImport
    extra = 0
    fields = ("trip_ref", "driver_ref", "earning_date", "gross", "commission", "net", "matched")


@admin.register(PlatformSettlement)
class PlatformSettlementAdmin(admin.ModelAdmin):
    list_display = (
        "settlement_no",
        "settlement_date",
        "platform",
        "gross_earnings",
        "commission",
        "net_received",
        "variance",
        "status",
    )
    list_filter = ("status", "entity", "platform")
    date_hierarchy = "settlement_date"
    inlines = [EarningImportInline]
    readonly_fields = ("settlement_no", "variance", "status", "journal_entry")


@admin.register(EarningImport)
class EarningImportAdmin(admin.ModelAdmin):
    list_display = ("platform", "trip_ref", "driver_ref", "earning_date", "gross", "net", "matched")
    list_filter = ("matched", "platform")
    date_hierarchy = "earning_date"
    search_fields = ("trip_ref", "driver_ref")
