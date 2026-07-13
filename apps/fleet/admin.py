"""Admin for the Fleet module."""

from django.contrib import admin

from apps.fleet.models import (
    DepreciationLine,
    DepreciationRun,
    Vehicle,
    VehicleDocument,
    VehicleLoan,
    VehicleLoanInstallment,
)


class VehicleDocumentInline(admin.TabularInline):
    model = VehicleDocument
    extra = 0


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ("code", "plate_no", "make", "model", "ownership", "entity", "is_active")
    list_filter = ("ownership", "is_active", "entity")
    search_fields = ("code", "plate_no", "vin")
    inlines = [VehicleDocumentInline]
    autocomplete_fields = (
        "entity",
        "asset_account",
        "depreciation_expense_account",
        "accumulated_depreciation_account",
    )


class VehicleLoanInstallmentInline(admin.TabularInline):
    model = VehicleLoanInstallment
    extra = 0
    readonly_fields = ("status", "journal_entry")


@admin.register(VehicleLoan)
class VehicleLoanAdmin(admin.ModelAdmin):
    list_display = ("vehicle", "lender", "principal", "emi_amount", "term_months", "is_active")
    list_filter = ("is_active", "entity")
    inlines = [VehicleLoanInstallmentInline]


class DepreciationLineInline(admin.TabularInline):
    model = DepreciationLine
    extra = 0
    readonly_fields = ("vehicle", "amount")


@admin.register(DepreciationRun)
class DepreciationRunAdmin(admin.ModelAdmin):
    list_display = ("run_no", "run_date", "period_label", "total_amount", "status")
    list_filter = ("status", "entity")
    date_hierarchy = "run_date"
    inlines = [DepreciationLineInline]
    readonly_fields = ("run_no", "total_amount", "status", "journal_entry")


@admin.register(VehicleDocument)
class VehicleDocumentAdmin(admin.ModelAdmin):
    list_display = ("vehicle", "doc_type", "doc_no", "issue_date", "expiry_date")
    list_filter = ("doc_type",)
    date_hierarchy = "expiry_date"
