"""Accounts Receivable (design doc 03 §ar).

Customers, sales invoices + lines, credit notes + lines, and receipt allocations.
Documents post through the ledger engine; balances/aging are derived from these
rows (the GL stays the source of truth).
"""

from django.db import models

from apps.core.models import BaseModel


class InvoiceStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    POSTED = "posted", "Posted"
    PARTIALLY_PAID = "partially_paid", "Partially paid"
    PAID = "paid", "Paid"
    CANCELLED = "cancelled", "Cancelled"


class Customer(BaseModel):
    entity = models.ForeignKey("tenants.Entity", on_delete=models.PROTECT, related_name="customers")
    code = models.CharField(max_length=24)
    name = models.CharField(max_length=255)
    trn = models.CharField(max_length=15, blank=True, db_index=True)
    customer_type = models.CharField(max_length=12, default="b2b")  # b2b/b2c/corporate/platform
    receivable_account = models.ForeignKey(
        "accounts.Account", on_delete=models.PROTECT, related_name="+"
    )
    currency = models.ForeignKey(
        "core.Currency", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    credit_limit = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    credit_days = models.PositiveSmallIntegerField(null=True, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=32, blank=True)
    address = models.CharField(max_length=512, blank=True)
    emirate = models.CharField(max_length=32, blank=True)
    opening_balance = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["entity", "code"]
        constraints = [
            models.UniqueConstraint(fields=["entity", "code"], name="ar_customer_unique_code"),
        ]

    def __str__(self):
        return f"{self.code} {self.name}"


class SalesInvoice(BaseModel):
    entity = models.ForeignKey(
        "tenants.Entity", on_delete=models.PROTECT, related_name="sales_invoices"
    )
    branch = models.ForeignKey(
        "tenants.Branch", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="invoices")
    invoice_no = models.CharField(max_length=24, blank=True)  # assigned at post
    invoice_date = models.DateField(db_index=True)
    due_date = models.DateField(null=True, blank=True)
    place_of_supply = models.CharField(max_length=32, blank=True)  # emirate -> VAT 201 box
    currency = models.ForeignKey(
        "core.Currency", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    fx_rate = models.DecimalField(max_digits=18, decimal_places=6, default=1)
    subtotal = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    tax_total = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    amount_allocated = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    balance = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    status = models.CharField(
        max_length=16, choices=InvoiceStatus.choices, default=InvoiceStatus.DRAFT, db_index=True
    )
    journal_entry = models.ForeignKey(
        "ledger.JournalEntry", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    narration = models.CharField(max_length=512, blank=True)

    class Meta:
        ordering = ["-invoice_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["entity", "invoice_no"],
                condition=models.Q(invoice_no__gt=""),
                name="ar_invoice_unique_no",
            ),
        ]

    def __str__(self):
        return f"INV {self.invoice_no or '(draft)'} {self.customer_id}"


class SalesInvoiceLine(BaseModel):
    invoice = models.ForeignKey(SalesInvoice, on_delete=models.CASCADE, related_name="lines")
    line_no = models.PositiveSmallIntegerField(default=0)
    revenue_account = models.ForeignKey(
        "accounts.Account", on_delete=models.PROTECT, related_name="+"
    )
    description = models.CharField(max_length=512, blank=True)
    quantity = models.DecimalField(max_digits=18, decimal_places=6, default=1)
    unit_price = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    line_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    tax_code = models.ForeignKey(
        "accounts.TaxCode", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    tax_rate = models.DecimalField(max_digits=6, decimal_places=3, default=0)  # snapshot
    tax_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    cost_center = models.ForeignKey(
        "tenants.CostCenter", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    vehicle_id = models.UUIDField(null=True, blank=True)
    driver_id = models.UUIDField(null=True, blank=True)
    platform_id = models.UUIDField(null=True, blank=True)

    class Meta:
        ordering = ["invoice", "line_no"]

    def __str__(self):
        return f"{self.revenue_account_id} {self.line_amount}"


class CreditNote(BaseModel):
    entity = models.ForeignKey(
        "tenants.Entity", on_delete=models.PROTECT, related_name="credit_notes"
    )
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="credit_notes")
    credit_note_no = models.CharField(max_length=24, blank=True)
    credit_note_date = models.DateField(db_index=True)
    original_invoice = models.ForeignKey(
        SalesInvoice, on_delete=models.PROTECT, null=True, blank=True, related_name="credit_notes"
    )
    reason = models.CharField(max_length=255, blank=True)
    subtotal = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    tax_total = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    status = models.CharField(
        max_length=16, choices=InvoiceStatus.choices, default=InvoiceStatus.DRAFT, db_index=True
    )
    journal_entry = models.ForeignKey(
        "ledger.JournalEntry", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )

    class Meta:
        ordering = ["-credit_note_date", "-created_at"]

    def __str__(self):
        return f"CN {self.credit_note_no or '(draft)'}"


class CreditNoteLine(BaseModel):
    credit_note = models.ForeignKey(CreditNote, on_delete=models.CASCADE, related_name="lines")
    line_no = models.PositiveSmallIntegerField(default=0)
    revenue_account = models.ForeignKey(
        "accounts.Account", on_delete=models.PROTECT, related_name="+"
    )
    description = models.CharField(max_length=512, blank=True)
    line_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    tax_code = models.ForeignKey(
        "accounts.TaxCode", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    tax_rate = models.DecimalField(max_digits=6, decimal_places=3, default=0)
    tax_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    class Meta:
        ordering = ["credit_note", "line_no"]


class ReceiptAllocation(BaseModel):
    """Links a receipt voucher / credit note / advance to a specific invoice."""

    class Source(models.TextChoices):
        RECEIPT_VOUCHER = "receipt_voucher", "Receipt voucher"
        CREDIT_NOTE = "credit_note", "Credit note"
        ADVANCE = "advance", "Advance"

    entity = models.ForeignKey(
        "tenants.Entity", on_delete=models.PROTECT, related_name="ar_allocations"
    )
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="allocations")
    source_type = models.CharField(max_length=16, choices=Source.choices)
    source_id = models.UUIDField(db_index=True)
    invoice = models.ForeignKey(SalesInvoice, on_delete=models.PROTECT, related_name="allocations")
    amount_allocated = models.DecimalField(max_digits=18, decimal_places=2)
    allocation_date = models.DateField()

    class Meta:
        ordering = ["-allocation_date", "-created_at"]

    def __str__(self):
        return f"{self.source_type} {self.amount_allocated} -> {self.invoice_id}"
