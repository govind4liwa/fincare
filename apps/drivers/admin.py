"""Admin for the Drivers module."""

from django.contrib import admin

from apps.drivers.models import Advance, Driver, DriverDocument, Settlement, SettlementDeduction


class DriverDocumentInline(admin.TabularInline):
    model = DriverDocument
    extra = 0


@admin.register(Driver)
class DriverAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "nationality",
        "basic_salary",
        "commission_rate",
        "entity",
        "is_active",
    )
    list_filter = ("is_active", "entity")
    search_fields = ("code", "name", "licence_no", "emirates_id")
    inlines = [DriverDocumentInline]


@admin.register(Advance)
class AdvanceAdmin(admin.ModelAdmin):
    list_display = (
        "advance_no",
        "advance_date",
        "driver",
        "amount",
        "recovered_amount",
        "balance",
        "status",
    )
    list_filter = ("status", "entity")
    search_fields = ("advance_no", "driver__code", "driver__name")
    date_hierarchy = "advance_date"
    readonly_fields = ("advance_no", "recovered_amount", "balance", "status", "journal_entry")


class SettlementDeductionInline(admin.TabularInline):
    model = SettlementDeduction
    extra = 0
    autocomplete_fields = ("account", "advance")


@admin.register(Settlement)
class SettlementAdmin(admin.ModelAdmin):
    list_display = (
        "settlement_no",
        "settlement_date",
        "driver",
        "gross_amount",
        "total_deductions",
        "net_amount",
        "status",
    )
    list_filter = ("status", "entity")
    date_hierarchy = "settlement_date"
    inlines = [SettlementDeductionInline]
    readonly_fields = ("settlement_no", "total_deductions", "net_amount", "status", "journal_entry")


@admin.register(DriverDocument)
class DriverDocumentAdmin(admin.ModelAdmin):
    list_display = ("driver", "doc_type", "doc_no", "issue_date", "expiry_date")
    list_filter = ("doc_type",)
    date_hierarchy = "expiry_date"
