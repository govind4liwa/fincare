"""Admin for the general ledger (posted entries are read-only)."""

from django.contrib import admin

from apps.ledger.models import AccountingPeriod, JournalEntry, JournalLine


@admin.register(AccountingPeriod)
class AccountingPeriodAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "entity",
        "fiscal_year",
        "period_no",
        "status",
        "start_date",
        "end_date",
    )
    list_filter = ("status", "fiscal_year", "entity")
    search_fields = ("name",)


class JournalLineInline(admin.TabularInline):
    model = JournalLine
    extra = 0
    fields = ("line_no", "account", "debit", "credit", "base_debit", "base_credit", "party_type")
    autocomplete_fields = ("account",)

    def has_change_permission(self, request, obj=None):
        return obj is None or obj.status not in {"posted", "reversed", "cancelled"}

    def has_delete_permission(self, request, obj=None):
        return obj is None or obj.status not in {"posted", "reversed", "cancelled"}


@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    list_display = ("entry_no", "entry_date", "entity", "status", "total_debit", "total_credit")
    list_filter = ("status", "basis", "source_type", "entity")
    search_fields = ("entry_no", "narration")
    date_hierarchy = "entry_date"
    inlines = [JournalLineInline]
    readonly_fields = ("entry_no", "total_debit", "total_credit", "posted_at", "posted_by")

    def has_delete_permission(self, request, obj=None):
        return obj is None or obj.status not in {"posted", "reversed", "cancelled"}
