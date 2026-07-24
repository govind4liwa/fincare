"""Voucher documents (design doc 02).

A Voucher carries balanced lines and posts **through** the ledger engine — it
never writes GL rows itself (ADR-0007). The five types (receipt/payment/contra/
expense/journal) differ only in convention; the debit/credit come from the lines.
"""

from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class VoucherType(models.TextChoices):
    RECEIPT = "receipt", "Receipt"
    PAYMENT = "payment", "Payment"
    CONTRA = "contra", "Contra"
    EXPENSE = "expense", "Expense"
    JOURNAL = "journal", "Journal"


class VoucherStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    POSTED = "posted", "Posted"
    REVERSED = "reversed", "Reversed"
    CANCELLED = "cancelled", "Cancelled"


# Per-type document-number prefix.
NUMBER_PREFIX = {
    VoucherType.RECEIPT: "RV-",
    VoucherType.PAYMENT: "PV-",
    VoucherType.CONTRA: "CV-",
    VoucherType.EXPENSE: "EV-",
    VoucherType.JOURNAL: "JV-",
}


class Voucher(BaseModel):
    entity = models.ForeignKey("tenants.Entity", on_delete=models.PROTECT, related_name="vouchers")
    branch = models.ForeignKey(
        "tenants.Branch", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    voucher_type = models.CharField(max_length=12, choices=VoucherType.choices, db_index=True)
    voucher_no = models.CharField(max_length=24, blank=True)  # assigned at post
    voucher_date = models.DateField(db_index=True)
    party_type = models.CharField(max_length=12, blank=True)  # customer / supplier / other
    party_id = models.UUIDField(null=True, blank=True)
    payment_mode = models.CharField(max_length=12, blank=True)  # cash/bank/card/cheque/online
    bank_account = models.ForeignKey(
        "accounts.Account", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    cheque_no = models.CharField(max_length=32, blank=True)
    reference = models.CharField(max_length=64, blank=True)
    narration = models.CharField(max_length=512, blank=True)
    currency = models.ForeignKey(
        "core.Currency", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    status = models.CharField(
        max_length=12, choices=VoucherStatus.choices, default=VoucherStatus.DRAFT, db_index=True
    )
    journal_entry = models.ForeignKey(
        "ledger.JournalEntry", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    posted_at = models.DateTimeField(null=True, blank=True)
    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        ordering = ["-voucher_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["entity", "voucher_type", "voucher_no"],
                condition=models.Q(voucher_no__gt=""),
                name="vouchers_voucher_unique_no",
            ),
        ]

    def __str__(self):
        return f"{self.get_voucher_type_display()} {self.voucher_no or '(draft)'}"


class VoucherLine(BaseModel):
    voucher = models.ForeignKey(Voucher, on_delete=models.CASCADE, related_name="lines")
    line_no = models.PositiveSmallIntegerField(default=0)
    account = models.ForeignKey("accounts.Account", on_delete=models.PROTECT, related_name="+")
    description = models.CharField(max_length=512, blank=True)
    debit = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    credit = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    cost_center = models.ForeignKey(
        "tenants.CostCenter", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    party_type = models.CharField(max_length=12, blank=True)  # overrides header for this line
    party_id = models.UUIDField(null=True, blank=True)
    vehicle_id = models.UUIDField(null=True, blank=True)
    driver_id = models.UUIDField(null=True, blank=True)
    platform_id = models.UUIDField(null=True, blank=True)
    tax_code = models.ForeignKey(
        "accounts.TaxCode", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )

    class Meta:
        ordering = ["voucher", "line_no"]

    def __str__(self):
        return f"{self.account_id} D{self.debit}/C{self.credit}"
