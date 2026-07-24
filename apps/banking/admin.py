"""Admin for the Banking module."""

from django.contrib import admin

from apps.banking.models import (
    BankAccount,
    BankStatement,
    BankTransfer,
    PosSettlement,
    Reconciliation,
    ReconciliationItem,
    StatementLine,
)


@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "bank_name", "entity", "is_active")
    list_filter = ("is_active", "entity")
    search_fields = ("code", "name", "account_number", "iban")
    autocomplete_fields = ("entity", "gl_account", "currency")


@admin.register(BankTransfer)
class BankTransferAdmin(admin.ModelAdmin):
    list_display = (
        "transfer_no",
        "transfer_date",
        "from_account",
        "to_account",
        "amount",
        "charges",
        "status",
    )
    list_filter = ("status", "entity")
    search_fields = ("transfer_no", "reference")
    date_hierarchy = "transfer_date"
    readonly_fields = ("transfer_no", "status", "journal_entry")


@admin.register(PosSettlement)
class PosSettlementAdmin(admin.ModelAdmin):
    list_display = (
        "settlement_no",
        "settlement_date",
        "bank_account",
        "gross_amount",
        "fee_amount",
        "net_amount",
        "status",
    )
    list_filter = ("status", "entity")
    date_hierarchy = "settlement_date"
    readonly_fields = ("settlement_no", "net_amount", "status", "journal_entry")


class StatementLineInline(admin.TabularInline):
    model = StatementLine
    extra = 0


@admin.register(BankStatement)
class BankStatementAdmin(admin.ModelAdmin):
    list_display = (
        "bank_account",
        "statement_date",
        "opening_balance",
        "closing_balance",
        "status",
    )
    list_filter = ("status", "entity")
    date_hierarchy = "statement_date"
    inlines = [StatementLineInline]


class ReconciliationItemInline(admin.TabularInline):
    model = ReconciliationItem
    extra = 0
    readonly_fields = ("statement_line", "journal_line", "match_type", "amount")


@admin.register(Reconciliation)
class ReconciliationAdmin(admin.ModelAdmin):
    list_display = (
        "bank_account",
        "recon_date",
        "statement_balance",
        "gl_balance",
        "difference",
        "status",
    )
    list_filter = ("status", "entity")
    date_hierarchy = "recon_date"
    inlines = [ReconciliationItemInline]
    readonly_fields = ("statement_balance", "gl_balance", "difference", "status")
