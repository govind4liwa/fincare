"""Banking module (design doc 06 §banking).

Bank accounts wrap a GL account; transfers, POS settlements, statement imports and
reconciliations all post through the ledger engine (ADR-0007) — banking never
writes GL rows directly. Reconciliation matches imported statement lines to posted
journal lines on the bank's GL account (rule: amount + date window + reference).
"""

from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class BankDocStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    POSTED = "posted", "Posted"
    REVERSED = "reversed", "Reversed"
    CANCELLED = "cancelled", "Cancelled"


class BankAccount(BaseModel):
    """A bank account, mapped 1:1 to a GL account (account_type='bank')."""

    entity = models.ForeignKey(
        "tenants.Entity", on_delete=models.PROTECT, related_name="bank_accounts"
    )
    code = models.CharField(max_length=24)
    name = models.CharField(max_length=128)
    gl_account = models.ForeignKey("accounts.Account", on_delete=models.PROTECT, related_name="+")
    bank_name = models.CharField(max_length=128, blank=True)
    account_number = models.CharField(max_length=64, blank=True)
    iban = models.CharField(max_length=34, blank=True)
    swift = models.CharField(max_length=11, blank=True)
    branch_name = models.CharField(max_length=128, blank=True)
    currency = models.ForeignKey(
        "core.Currency", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["entity", "code"]
        constraints = [
            models.UniqueConstraint(
                fields=["entity", "code"], name="banking_bankaccount_unique_code"
            )
        ]

    def __str__(self):
        return f"{self.code} {self.name}"


class BankTransfer(BaseModel):
    """Move funds between two bank/cash GL accounts; bank charges optional.

    Posting: DR destination GL (amount) / DR charge account (charges) /
    CR source GL (amount + charges).
    """

    entity = models.ForeignKey(
        "tenants.Entity", on_delete=models.PROTECT, related_name="bank_transfers"
    )
    transfer_no = models.CharField(max_length=24, blank=True)
    transfer_date = models.DateField(db_index=True)
    from_account = models.ForeignKey(
        BankAccount, on_delete=models.PROTECT, related_name="transfers_out"
    )
    to_account = models.ForeignKey(
        BankAccount, on_delete=models.PROTECT, related_name="transfers_in"
    )
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    charges = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    charge_account = models.ForeignKey(
        "accounts.Account", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    reference = models.CharField(max_length=64, blank=True)
    narration = models.CharField(max_length=512, blank=True)
    status = models.CharField(
        max_length=12, choices=BankDocStatus.choices, default=BankDocStatus.DRAFT, db_index=True
    )
    journal_entry = models.ForeignKey(
        "ledger.JournalEntry", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )

    class Meta:
        ordering = ["-transfer_date", "-created_at"]

    def __str__(self):
        return f"TRF {self.transfer_no or '(draft)'} {self.amount}"


class PosSettlement(BaseModel):
    """Card-machine / acquirer settlement.

    Posting: DR Bank (net) / DR Fee expense (fee) / CR POS Clearing (gross).
    The POS clearing account is debited by card sales at point of sale and
    cleared here when the acquirer deposits the net into the bank.
    """

    entity = models.ForeignKey(
        "tenants.Entity", on_delete=models.PROTECT, related_name="pos_settlements"
    )
    settlement_no = models.CharField(max_length=24, blank=True)
    settlement_date = models.DateField(db_index=True)
    bank_account = models.ForeignKey(
        BankAccount, on_delete=models.PROTECT, related_name="pos_settlements"
    )
    gross_amount = models.DecimalField(max_digits=18, decimal_places=2)
    fee_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    net_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    fee_account = models.ForeignKey(
        "accounts.Account", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    pos_clearing_account = models.ForeignKey(
        "accounts.Account", on_delete=models.PROTECT, related_name="+"
    )
    reference = models.CharField(max_length=64, blank=True)
    status = models.CharField(
        max_length=12, choices=BankDocStatus.choices, default=BankDocStatus.DRAFT, db_index=True
    )
    journal_entry = models.ForeignKey(
        "ledger.JournalEntry", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )

    class Meta:
        ordering = ["-settlement_date", "-created_at"]

    def __str__(self):
        return f"POS {self.settlement_no or '(draft)'} net={self.net_amount}"


class BankStatement(BaseModel):
    """An imported bank statement (header)."""

    class Status(models.TextChoices):
        IMPORTED = "imported", "Imported"
        RECONCILED = "reconciled", "Reconciled"

    entity = models.ForeignKey(
        "tenants.Entity", on_delete=models.PROTECT, related_name="bank_statements"
    )
    bank_account = models.ForeignKey(
        BankAccount, on_delete=models.PROTECT, related_name="statements"
    )
    statement_no = models.CharField(max_length=64, blank=True)
    statement_date = models.DateField(db_index=True)
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)
    opening_balance = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    closing_balance = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.IMPORTED, db_index=True
    )

    class Meta:
        ordering = ["-statement_date", "-created_at"]

    def __str__(self):
        return f"Statement {self.bank_account_id} {self.statement_date}"


class StatementLine(BaseModel):
    """One line of an imported bank statement.

    ``deposit`` = money into the account (matches a DEBIT on the bank GL);
    ``withdrawal`` = money out (matches a CREDIT on the bank GL).
    """

    statement = models.ForeignKey(BankStatement, on_delete=models.CASCADE, related_name="lines")
    line_no = models.PositiveSmallIntegerField(default=0)
    txn_date = models.DateField(db_index=True)
    value_date = models.DateField(null=True, blank=True)
    description = models.CharField(max_length=512, blank=True)
    reference = models.CharField(max_length=64, blank=True)
    deposit = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    withdrawal = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    running_balance = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    is_matched = models.BooleanField(default=False, db_index=True)

    class Meta:
        ordering = ["statement", "line_no"]

    def __str__(self):
        return f"{self.txn_date} +{self.deposit}/-{self.withdrawal}"


class Reconciliation(BaseModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"

    entity = models.ForeignKey(
        "tenants.Entity", on_delete=models.PROTECT, related_name="reconciliations"
    )
    bank_account = models.ForeignKey(
        BankAccount, on_delete=models.PROTECT, related_name="reconciliations"
    )
    statement = models.ForeignKey(
        BankStatement,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reconciliations",
    )
    recon_date = models.DateField(db_index=True)
    statement_balance = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    gl_balance = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    difference = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.DRAFT, db_index=True
    )
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        ordering = ["-recon_date", "-created_at"]

    def __str__(self):
        return f"Recon {self.bank_account_id} {self.recon_date} [{self.status}]"


class ReconciliationItem(BaseModel):
    """A matched pair: one statement line <-> one bank GL journal line."""

    class MatchType(models.TextChoices):
        AUTO = "auto", "Auto"
        MANUAL = "manual", "Manual"

    reconciliation = models.ForeignKey(
        Reconciliation, on_delete=models.CASCADE, related_name="items"
    )
    statement_line = models.ForeignKey(
        StatementLine, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    journal_line = models.ForeignKey(
        "ledger.JournalLine", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    match_type = models.CharField(max_length=8, choices=MatchType.choices, default=MatchType.AUTO)
    amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    class Meta:
        ordering = ["reconciliation", "created_at"]

    def __str__(self):
        return f"{self.match_type} {self.amount}"
