"""Drivers module (design doc 04 §drivers).

Drivers, their documents (visa, Emirates ID, licence), cash advances (recoverable),
and periodic settlements. A settlement nets the driver's gross earnings against
deductions (commission, salary, advance recovery, Salik, fines) and posts the
payout. Postings carry the ``driver_id`` (and optional ``vehicle_id``) profitability
dimensions. All financial events post through the ledger engine (ADR-0007).
"""

from django.db import models

from apps.core.models import BaseModel


class DriverDocStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    POSTED = "posted", "Posted"
    REVERSED = "reversed", "Reversed"
    CANCELLED = "cancelled", "Cancelled"


class Driver(BaseModel):
    """A driver. Its id is the ``driver_id`` profitability dimension."""

    entity = models.ForeignKey("tenants.Entity", on_delete=models.PROTECT, related_name="drivers")
    code = models.CharField(max_length=24)
    name = models.CharField(max_length=255)
    nationality = models.CharField(max_length=64, blank=True)
    licence_no = models.CharField(max_length=64, blank=True)
    emirates_id = models.CharField(max_length=32, blank=True)
    phone = models.CharField(max_length=32, blank=True)
    basic_salary = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    commission_rate = models.DecimalField(max_digits=6, decimal_places=3, default=0)  # %
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["entity", "code"]
        constraints = [
            models.UniqueConstraint(fields=["entity", "code"], name="drivers_driver_unique_code"),
        ]

    def __str__(self):
        return f"{self.code} {self.name}"


class DriverDocument(BaseModel):
    class DocType(models.TextChoices):
        VISA = "visa", "Residence Visa"
        EMIRATES_ID = "emirates_id", "Emirates ID"
        LICENCE = "licence", "Driving Licence"
        PASSPORT = "passport", "Passport"
        HEALTH = "health", "Health Insurance"
        OTHER = "other", "Other"

    driver = models.ForeignKey(Driver, on_delete=models.CASCADE, related_name="documents")
    doc_type = models.CharField(max_length=16, choices=DocType.choices)
    doc_no = models.CharField(max_length=64, blank=True)
    issue_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True, db_index=True)
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["driver", "expiry_date"]

    def __str__(self):
        return f"{self.driver_id} {self.doc_type} exp {self.expiry_date}"


class Advance(BaseModel):
    """A cash advance to a driver, recovered later (typically via settlement).

    Posting: DR Driver Advance (asset, driver dim) / CR Bank.
    """

    entity = models.ForeignKey(
        "tenants.Entity", on_delete=models.PROTECT, related_name="driver_advances"
    )
    driver = models.ForeignKey(Driver, on_delete=models.PROTECT, related_name="advances")
    advance_no = models.CharField(max_length=24, blank=True)
    advance_date = models.DateField(db_index=True)
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    recovered_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    balance = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    advance_account = models.ForeignKey(
        "accounts.Account", on_delete=models.PROTECT, related_name="+"
    )
    bank_account = models.ForeignKey(
        "banking.BankAccount", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    status = models.CharField(
        max_length=12, choices=DriverDocStatus.choices, default=DriverDocStatus.DRAFT, db_index=True
    )
    journal_entry = models.ForeignKey(
        "ledger.JournalEntry", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )

    class Meta:
        ordering = ["-advance_date", "-created_at"]

    def __str__(self):
        return f"ADV {self.advance_no or '(draft)'} {self.amount}"


class Settlement(BaseModel):
    """A driver settlement for a period.

    ``net_amount = gross_amount − Σ deductions`` (commission, salary, advance
    recovery, Salik, fines, other). Posting:
        DR  gross_account (driver/vehicle dim)   = gross
        CR  each deduction account               = deduction amount
        CR  bank (pay account)                   = net   (net > 0 → pay driver)
        DR  bank (pay account)                   = -net  (net < 0 → driver pays in)
    """

    entity = models.ForeignKey(
        "tenants.Entity", on_delete=models.PROTECT, related_name="settlements"
    )
    driver = models.ForeignKey(Driver, on_delete=models.PROTECT, related_name="settlements")
    vehicle = models.ForeignKey(
        "fleet.Vehicle", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    settlement_no = models.CharField(max_length=24, blank=True)
    period_start = models.DateField()
    period_end = models.DateField()
    settlement_date = models.DateField(db_index=True)
    gross_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    gross_account = models.ForeignKey(
        "accounts.Account", on_delete=models.PROTECT, related_name="+"
    )
    pay_account = models.ForeignKey(
        "banking.BankAccount", on_delete=models.PROTECT, related_name="+"
    )
    total_deductions = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    net_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    status = models.CharField(
        max_length=12, choices=DriverDocStatus.choices, default=DriverDocStatus.DRAFT, db_index=True
    )
    journal_entry = models.ForeignKey(
        "ledger.JournalEntry", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )

    class Meta:
        ordering = ["-settlement_date", "-created_at"]

    def __str__(self):
        return f"SETL {self.settlement_no or '(draft)'} net={self.net_amount}"


class SettlementDeduction(BaseModel):
    """A single deduction line on a settlement."""

    class Kind(models.TextChoices):
        COMMISSION = "commission", "Commission"
        SALARY = "salary", "Salary"
        ADVANCE = "advance", "Advance recovery"
        SALIK = "salik", "Salik recovery"
        FINE = "fine", "Fine recovery"
        OTHER = "other", "Other"

    settlement = models.ForeignKey(Settlement, on_delete=models.CASCADE, related_name="deductions")
    kind = models.CharField(max_length=12, choices=Kind.choices)
    account = models.ForeignKey("accounts.Account", on_delete=models.PROTECT, related_name="+")
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    advance = models.ForeignKey(
        Advance, on_delete=models.PROTECT, null=True, blank=True, related_name="recoveries"
    )
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["settlement", "kind"]

    def __str__(self):
        return f"{self.kind} {self.amount}"
