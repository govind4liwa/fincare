"""Admin for Accounts Payable."""

from django.contrib import admin

from apps.ap.models import (
    DebitNote,
    DebitNoteLine,
    PaymentAllocation,
    PurchaseBill,
    PurchaseBillLine,
    Supplier,
)


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "trn", "entity", "is_active")
    list_filter = ("is_active", "entity")
    search_fields = ("code", "name", "trn")
    autocomplete_fields = ("entity", "payable_account", "currency")


class PurchaseBillLineInline(admin.TabularInline):
    model = PurchaseBillLine
    extra = 0
    autocomplete_fields = ("account", "tax_code")


@admin.register(PurchaseBill)
class PurchaseBillAdmin(admin.ModelAdmin):
    list_display = (
        "bill_no",
        "bill_date",
        "supplier",
        "total",
        "balance",
        "is_reverse_charge",
        "status",
    )
    list_filter = ("status", "is_reverse_charge", "entity")
    search_fields = ("bill_no", "supplier_invoice_no")
    date_hierarchy = "bill_date"
    inlines = [PurchaseBillLineInline]
    readonly_fields = (
        "bill_no",
        "subtotal",
        "tax_total",
        "total",
        "amount_allocated",
        "balance",
        "status",
        "journal_entry",
    )


class DebitNoteLineInline(admin.TabularInline):
    model = DebitNoteLine
    extra = 0
    autocomplete_fields = ("account", "tax_code")


@admin.register(DebitNote)
class DebitNoteAdmin(admin.ModelAdmin):
    list_display = ("debit_note_no", "debit_note_date", "supplier", "total", "status")
    list_filter = ("status", "entity")
    search_fields = ("debit_note_no",)
    inlines = [DebitNoteLineInline]
    readonly_fields = ("debit_note_no", "subtotal", "tax_total", "total", "status", "journal_entry")


@admin.register(PaymentAllocation)
class PaymentAllocationAdmin(admin.ModelAdmin):
    list_display = ("bill", "source_type", "amount_allocated", "allocation_date")
    list_filter = ("source_type",)
