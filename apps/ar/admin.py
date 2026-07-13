"""Admin for Accounts Receivable."""

from django.contrib import admin

from apps.ar.models import (
    CreditNote,
    CreditNoteLine,
    Customer,
    ReceiptAllocation,
    SalesInvoice,
    SalesInvoiceLine,
)


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "trn", "entity", "is_active")
    list_filter = ("customer_type", "is_active", "entity")
    search_fields = ("code", "name", "trn")
    autocomplete_fields = ("entity", "receivable_account", "currency")


class SalesInvoiceLineInline(admin.TabularInline):
    model = SalesInvoiceLine
    extra = 0
    autocomplete_fields = ("revenue_account", "tax_code")


@admin.register(SalesInvoice)
class SalesInvoiceAdmin(admin.ModelAdmin):
    list_display = ("invoice_no", "invoice_date", "customer", "total", "balance", "status")
    list_filter = ("status", "entity")
    search_fields = ("invoice_no", "narration")
    date_hierarchy = "invoice_date"
    inlines = [SalesInvoiceLineInline]
    readonly_fields = (
        "invoice_no",
        "subtotal",
        "tax_total",
        "total",
        "amount_allocated",
        "balance",
        "status",
        "journal_entry",
    )


class CreditNoteLineInline(admin.TabularInline):
    model = CreditNoteLine
    extra = 0
    autocomplete_fields = ("revenue_account", "tax_code")


@admin.register(CreditNote)
class CreditNoteAdmin(admin.ModelAdmin):
    list_display = ("credit_note_no", "credit_note_date", "customer", "total", "status")
    list_filter = ("status", "entity")
    search_fields = ("credit_note_no",)
    inlines = [CreditNoteLineInline]
    readonly_fields = (
        "credit_note_no",
        "subtotal",
        "tax_total",
        "total",
        "status",
        "journal_entry",
    )


@admin.register(ReceiptAllocation)
class ReceiptAllocationAdmin(admin.ModelAdmin):
    list_display = ("invoice", "source_type", "amount_allocated", "allocation_date")
    list_filter = ("source_type",)
