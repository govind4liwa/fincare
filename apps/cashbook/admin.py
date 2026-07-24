"""Admin for the Cashbook module."""

from django.contrib import admin

from apps.cashbook.models import CashAccount, CashCount, Denomination, PettyCashFloat, Replenishment


@admin.register(CashAccount)
class CashAccountAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "entity", "is_active")
    list_filter = ("is_active", "entity")
    search_fields = ("code", "name")
    autocomplete_fields = ("entity", "gl_account", "branch")


@admin.register(PettyCashFloat)
class PettyCashFloatAdmin(admin.ModelAdmin):
    list_display = ("code", "cash_account", "float_amount", "custodian", "is_active")
    list_filter = ("is_active", "entity")


@admin.register(Replenishment)
class ReplenishmentAdmin(admin.ModelAdmin):
    list_display = (
        "replenish_no",
        "replenish_date",
        "petty_cash_float",
        "bank_account",
        "amount",
        "status",
    )
    list_filter = ("status", "entity")
    date_hierarchy = "replenish_date"
    readonly_fields = ("replenish_no", "status", "journal_entry")


class DenominationInline(admin.TabularInline):
    model = Denomination
    extra = 0


@admin.register(CashCount)
class CashCountAdmin(admin.ModelAdmin):
    list_display = (
        "count_no",
        "count_date",
        "cash_account",
        "expected_amount",
        "counted_amount",
        "variance",
        "status",
    )
    list_filter = ("status", "entity")
    date_hierarchy = "count_date"
    inlines = [DenominationInline]
    readonly_fields = ("count_no", "counted_amount", "variance", "status", "journal_entry")
