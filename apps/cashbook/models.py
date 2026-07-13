"""Cashbook module (design doc 06 §cashbook).

Cash accounts wrap a GL account (account_type='cash'). Petty-cash floats run on
the imprest system: replenishments top the float back up (DR Petty Cash / CR Bank),
and physical cash counts post any variance to a short/over account. All movements
post through the ledger engine (ADR-0007).
"""

from django.db import models

from apps.core.models import BaseModel


class CashDocStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    POSTED = "posted", "Posted"
    REVERSED = "reversed", "Reversed"
    CANCELLED = "cancelled", "Cancelled"


class CashAccount(BaseModel):
    """A physical cash drawer / till, mapped to a GL account (account_type='cash')."""

    entity = models.ForeignKey(
        "tenants.Entity", on_delete=models.PROTECT, related_name="cash_accounts"
    )
    code = models.CharField(max_length=24)
    name = models.CharField(max_length=128)
    gl_account = models.ForeignKey("accounts.Account", on_delete=models.PROTECT, related_name="+")
    branch = models.ForeignKey(
        "tenants.Branch", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["entity", "code"]
        constraints = [
            models.UniqueConstraint(
                fields=["entity", "code"], name="cashbook_cashaccount_unique_code"
            )
        ]

    def __str__(self):
        return f"{self.code} {self.name}"


class PettyCashFloat(BaseModel):
    """An imprest petty-cash float held in a cash account."""

    entity = models.ForeignKey(
        "tenants.Entity", on_delete=models.PROTECT, related_name="petty_cash_floats"
    )
    cash_account = models.ForeignKey(CashAccount, on_delete=models.PROTECT, related_name="floats")
    code = models.CharField(max_length=24)
    float_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    custodian = models.CharField(max_length=128, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["entity", "code"]
        constraints = [
            models.UniqueConstraint(
                fields=["entity", "code"], name="cashbook_pettyfloat_unique_code"
            )
        ]

    def __str__(self):
        return f"{self.code} float={self.float_amount}"


class Replenishment(BaseModel):
    """Top up a petty-cash float from a bank account. DR Petty Cash / CR Bank."""

    entity = models.ForeignKey(
        "tenants.Entity", on_delete=models.PROTECT, related_name="replenishments"
    )
    petty_cash_float = models.ForeignKey(
        PettyCashFloat, on_delete=models.PROTECT, related_name="replenishments"
    )
    bank_account = models.ForeignKey(
        "banking.BankAccount", on_delete=models.PROTECT, related_name="replenishments"
    )
    replenish_no = models.CharField(max_length=24, blank=True)
    replenish_date = models.DateField(db_index=True)
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    reference = models.CharField(max_length=64, blank=True)
    status = models.CharField(
        max_length=12, choices=CashDocStatus.choices, default=CashDocStatus.DRAFT, db_index=True
    )
    journal_entry = models.ForeignKey(
        "ledger.JournalEntry", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )

    class Meta:
        ordering = ["-replenish_date", "-created_at"]

    def __str__(self):
        return f"REP {self.replenish_no or '(draft)'} {self.amount}"


class CashCount(BaseModel):
    """A physical count of a cash account; variance posts to a short/over account.

    ``counted_amount`` is the sum of denomination lines. Variance =
    counted − expected. Shortage (negative) posts DR short/over, CR cash;
    overage (positive) posts DR cash, CR short/over.
    """

    entity = models.ForeignKey(
        "tenants.Entity", on_delete=models.PROTECT, related_name="cash_counts"
    )
    cash_account = models.ForeignKey(CashAccount, on_delete=models.PROTECT, related_name="counts")
    count_no = models.CharField(max_length=24, blank=True)
    count_date = models.DateField(db_index=True)
    counted_by = models.CharField(max_length=128, blank=True)
    expected_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    counted_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    variance = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    variance_account = models.ForeignKey(
        "accounts.Account", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    status = models.CharField(
        max_length=12, choices=CashDocStatus.choices, default=CashDocStatus.DRAFT, db_index=True
    )
    journal_entry = models.ForeignKey(
        "ledger.JournalEntry", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )

    class Meta:
        ordering = ["-count_date", "-created_at"]

    def __str__(self):
        return f"COUNT {self.count_no or '(draft)'} var={self.variance}"


class Denomination(BaseModel):
    """A single denomination tally line of a cash count."""

    cash_count = models.ForeignKey(
        CashCount, on_delete=models.CASCADE, related_name="denominations"
    )
    denomination_value = models.DecimalField(max_digits=10, decimal_places=2)  # e.g. 1000, 0.25
    quantity = models.PositiveIntegerField(default=0)
    amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    class Meta:
        ordering = ["cash_count", "-denomination_value"]

    def __str__(self):
        return f"{self.denomination_value} x {self.quantity} = {self.amount}"
