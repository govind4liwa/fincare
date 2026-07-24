"""Accounts Payable (design doc 03 §ap).

Suppliers, purchase bills + lines (with reverse-charge and recoverable-VAT flags),
debit notes + lines, and payment allocations. Documents post through the ledger
engine; balances/aging are derived.
"""

from django.db import models

from apps.core.models import BaseModel


class BillStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    POSTED = "posted", "Posted"
    PARTIALLY_PAID = "partially_paid", "Partially paid"
    PAID = "paid", "Paid"
    CANCELLED = "cancelled", "Cancelled"


class Supplier(BaseModel):
    entity = models.ForeignKey("tenants.Entity", on_delete=models.PROTECT, related_name="suppliers")
    code = models.CharField(max_length=24)
    name = models.CharField(max_length=255)
    trn = models.CharField(max_length=15, blank=True, db_index=True)
    payable_account = models.ForeignKey(
        "accounts.Account", on_delete=models.PROTECT, related_name="+"
    )
    currency = models.ForeignKey(
        "core.Currency", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    credit_days = models.PositiveSmallIntegerField(null=True, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=32, blank=True)
    address = models.CharField(max_length=512, blank=True)
    opening_balance = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["entity", "code"]
        constraints = [
            models.UniqueConstraint(fields=["entity", "code"], name="ap_supplier_unique_code"),
        ]

    def __str__(self):
        return f"{self.code} {self.name}"


class PurchaseBill(BaseModel):
    entity = models.ForeignKey(
        "tenants.Entity", on_delete=models.PROTECT, related_name="purchase_bills"
    )
    branch = models.ForeignKey(
        "tenants.Branch", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="bills")
    bill_no = models.CharField(max_length=24, blank=True)  # internal, assigned at post
    supplier_invoice_no = models.CharField(max_length=64, blank=True)
    bill_date = models.DateField(db_index=True)
    due_date = models.DateField(null=True, blank=True)
    currency = models.ForeignKey(
        "core.Currency", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    fx_rate = models.DecimalField(max_digits=18, decimal_places=6, default=1)
    subtotal = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    tax_total = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    amount_allocated = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    balance = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    is_reverse_charge = models.BooleanField(default=False)  # import / RCM
    status = models.CharField(
        max_length=16, choices=BillStatus.choices, default=BillStatus.DRAFT, db_index=True
    )
    journal_entry = models.ForeignKey(
        "ledger.JournalEntry", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )

    class Meta:
        ordering = ["-bill_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["entity", "bill_no"],
                condition=models.Q(bill_no__gt=""),
                name="ap_bill_unique_no",
            ),
        ]

    def __str__(self):
        return f"BILL {self.bill_no or '(draft)'} {self.supplier_id}"


class PurchaseBillLine(BaseModel):
    bill = models.ForeignKey(PurchaseBill, on_delete=models.CASCADE, related_name="lines")
    line_no = models.PositiveSmallIntegerField(default=0)
    account = models.ForeignKey("accounts.Account", on_delete=models.PROTECT, related_name="+")
    description = models.CharField(max_length=512, blank=True)
    quantity = models.DecimalField(max_digits=18, decimal_places=6, default=1)
    unit_price = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    line_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    tax_code = models.ForeignKey(
        "accounts.TaxCode", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    tax_rate = models.DecimalField(max_digits=6, decimal_places=3, default=0)
    tax_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    recoverable = models.BooleanField(default=True)  # input VAT recoverable?
    cost_center = models.ForeignKey(
        "tenants.CostCenter", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    vehicle_id = models.UUIDField(null=True, blank=True)
    driver_id = models.UUIDField(null=True, blank=True)

    class Meta:
        ordering = ["bill", "line_no"]

    def __str__(self):
        return f"{self.account_id} {self.line_amount}"


class DebitNote(BaseModel):
    entity = models.ForeignKey(
        "tenants.Entity", on_delete=models.PROTECT, related_name="debit_notes"
    )
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="debit_notes")
    debit_note_no = models.CharField(max_length=24, blank=True)
    debit_note_date = models.DateField(db_index=True)
    original_bill = models.ForeignKey(
        PurchaseBill, on_delete=models.PROTECT, null=True, blank=True, related_name="debit_notes"
    )
    reason = models.CharField(max_length=255, blank=True)
    subtotal = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    tax_total = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    status = models.CharField(
        max_length=16, choices=BillStatus.choices, default=BillStatus.DRAFT, db_index=True
    )
    journal_entry = models.ForeignKey(
        "ledger.JournalEntry", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )

    class Meta:
        ordering = ["-debit_note_date", "-created_at"]

    def __str__(self):
        return f"DN {self.debit_note_no or '(draft)'}"


class DebitNoteLine(BaseModel):
    debit_note = models.ForeignKey(DebitNote, on_delete=models.CASCADE, related_name="lines")
    line_no = models.PositiveSmallIntegerField(default=0)
    account = models.ForeignKey("accounts.Account", on_delete=models.PROTECT, related_name="+")
    description = models.CharField(max_length=512, blank=True)
    line_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    tax_code = models.ForeignKey(
        "accounts.TaxCode", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    tax_rate = models.DecimalField(max_digits=6, decimal_places=3, default=0)
    tax_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    class Meta:
        ordering = ["debit_note", "line_no"]


class PaymentAllocation(BaseModel):
    """Links a payment voucher / debit note / advance to a specific bill."""

    class Source(models.TextChoices):
        PAYMENT_VOUCHER = "payment_voucher", "Payment voucher"
        DEBIT_NOTE = "debit_note", "Debit note"
        ADVANCE = "advance", "Advance"

    entity = models.ForeignKey(
        "tenants.Entity", on_delete=models.PROTECT, related_name="ap_allocations"
    )
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="allocations")
    source_type = models.CharField(max_length=16, choices=Source.choices)
    source_id = models.UUIDField(db_index=True)
    bill = models.ForeignKey(PurchaseBill, on_delete=models.PROTECT, related_name="allocations")
    amount_allocated = models.DecimalField(max_digits=18, decimal_places=2)
    allocation_date = models.DateField()

    class Meta:
        ordering = ["-allocation_date", "-created_at"]

    def __str__(self):
        return f"{self.source_type} {self.amount_allocated} -> {self.bill_id}"
