"""Chart of Accounts (design doc 01, ADR-0004/0005).

Hierarchy: AccountGroup level 1 (Main) -> level 2 (Sub) -> Account (Charge leaf).
Account codes follow the fixed pattern EEE-MMM-SSS-CCC and are composed/validated
by ``apps.accounts.services.coding``. Balances are NOT stored here — they are
derived from the ledger.
"""

from django.db import models

from apps.core.models import BaseModel

CODE_REGEX = r"^\d{3}-\d{3}-\d{3}-\d{3}$"


class Nature(models.TextChoices):
    ASSET = "asset", "Asset"
    LIABILITY = "liability", "Liability"
    EQUITY = "equity", "Equity"
    INCOME = "income", "Income"
    EXPENSE = "expense", "Expense"


class AccountGroup(BaseModel):
    """Main (level 1) or Sub (level 2) tier of the COA."""

    entity = models.ForeignKey(
        "tenants.Entity", on_delete=models.PROTECT, related_name="account_groups"
    )
    level = models.PositiveSmallIntegerField()  # 1 = Main, 2 = Sub
    segment = models.CharField(max_length=3)  # this tier's 3-digit segment
    parent = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="children"
    )
    code = models.CharField(max_length=12)  # composed to this tier: "101-100" or "101-100-110"
    name = models.CharField(max_length=128)
    nature = models.CharField(max_length=12, choices=Nature.choices)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["entity", "code"]
        constraints = [
            models.UniqueConstraint(
                fields=["entity", "level", "segment", "parent"],
                name="accounts_group_unique_segment",
            ),
        ]

    def __str__(self):
        return f"{self.code} {self.name}"


class Account(BaseModel):
    """Postable charge-code leaf of the COA."""

    class AccountType(models.TextChoices):
        BANK = "bank", "Bank"
        CASH = "cash", "Cash"
        RECEIVABLE = "receivable", "Receivable"
        PAYABLE = "payable", "Payable"
        VAT_INPUT = "vat_input", "Input VAT"
        VAT_OUTPUT = "vat_output", "Output VAT"
        FIXED_ASSET = "fixed_asset", "Fixed Asset"
        LOAN = "loan", "Loan"
        REVENUE = "revenue", "Revenue"
        EXPENSE = "expense", "Expense"
        EQUITY = "equity", "Equity"
        GENERAL = "general", "General"

    entity = models.ForeignKey("tenants.Entity", on_delete=models.PROTECT, related_name="accounts")
    sub_group = models.ForeignKey(AccountGroup, on_delete=models.PROTECT, related_name="accounts")
    charge_segment = models.CharField(max_length=3)
    code = models.CharField(max_length=15, unique=True)  # EEE-MMM-SSS-CCC
    name = models.CharField(max_length=128)
    account_type = models.CharField(max_length=24, choices=AccountType.choices)
    normal_balance = models.CharField(max_length=1)  # 'D' or 'C'
    currency = models.ForeignKey(
        "core.Currency", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    is_control_account = models.BooleanField(default=False)
    subledger = models.CharField(max_length=16, blank=True)  # customer / supplier / ""
    is_bank_account = models.BooleanField(default=False)
    allow_manual_posting = models.BooleanField(default=True)
    is_postable = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(
                fields=["entity", "sub_group", "charge_segment"],
                name="accounts_account_unique_charge",
            ),
            models.CheckConstraint(
                condition=models.Q(code__regex=CODE_REGEX),
                name="accounts_account_code_format",
            ),
        ]

    def __str__(self):
        return f"{self.code} {self.name}"


class TaxCode(BaseModel):
    """UAE VAT treatment attachable to document lines (config-driven, no literals)."""

    class Treatment(models.TextChoices):
        STANDARD = "standard", "Standard rated"
        ZERO = "zero", "Zero rated"
        EXEMPT = "exempt", "Exempt"
        OUT_OF_SCOPE = "out_of_scope", "Out of scope"
        REVERSE_CHARGE = "reverse_charge", "Reverse charge"

    class Direction(models.TextChoices):
        INPUT = "input", "Input"
        OUTPUT = "output", "Output"
        BOTH = "both", "Both"

    entity = models.ForeignKey("tenants.Entity", on_delete=models.PROTECT, related_name="tax_codes")
    code = models.CharField(max_length=16)  # SR/ZR/EX/OS/RC/NA
    name = models.CharField(max_length=64)
    rate = models.DecimalField(max_digits=6, decimal_places=3, default=0)
    treatment = models.CharField(max_length=16, choices=Treatment.choices)
    direction = models.CharField(max_length=8, choices=Direction.choices, default=Direction.BOTH)
    account = models.ForeignKey(
        Account, on_delete=models.PROTECT, null=True, blank=True, related_name="tax_codes"
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["entity", "code"]
        constraints = [
            models.UniqueConstraint(fields=["entity", "code"], name="accounts_taxcode_unique"),
        ]

    def __str__(self):
        return f"{self.code} ({self.rate}%)"
