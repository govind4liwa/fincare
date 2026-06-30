"""Admin for vouchers (posted vouchers are read-only)."""

from django.contrib import admin

from apps.vouchers.models import Voucher, VoucherLine


class VoucherLineInline(admin.TabularInline):
    model = VoucherLine
    extra = 0
    fields = ("line_no", "account", "debit", "credit", "party_type", "tax_code")
    autocomplete_fields = ("account",)


@admin.register(Voucher)
class VoucherAdmin(admin.ModelAdmin):
    list_display = ("voucher_no", "voucher_type", "voucher_date", "entity", "amount", "status")
    list_filter = ("voucher_type", "status", "entity")
    search_fields = ("voucher_no", "reference", "narration")
    date_hierarchy = "voucher_date"
    inlines = [VoucherLineInline]
    readonly_fields = ("voucher_no", "amount", "status", "journal_entry", "posted_at", "posted_by")

    def has_delete_permission(self, request, obj=None):
        return obj is None or obj.status not in {"posted", "reversed"}
