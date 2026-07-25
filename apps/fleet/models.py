"""Fleet module (design doc 04 §fleet).

Vehicles, their documents (with expiry alerts), finance loans (EMI posts split
principal/interest against the bank), and depreciation runs. Vehicle cost
postings carry the vehicle profitability dimension (``vehicle_id`` on journal
lines) so the GL drives per-vehicle profitability. All financial events post
through the ledger engine (ADR-0007).
"""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import models

from apps.core.models import BaseModel

TWO_PLACES = Decimal("0.01")


class FleetDocStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    POSTED = "posted", "Posted"
    REVERSED = "reversed", "Reversed"
    CANCELLED = "cancelled", "Cancelled"


class Vehicle(BaseModel):
    """A fleet vehicle. Its id is the ``vehicle_id`` profitability dimension."""

    class Ownership(models.TextChoices):
        OWNED = "owned", "Owned"
        LEASED = "leased", "Leased"
        FINANCED = "financed", "Financed"

    entity = models.ForeignKey("tenants.Entity", on_delete=models.PROTECT, related_name="vehicles")
    code = models.CharField(max_length=24)  # internal fleet no
    plate_no = models.CharField(max_length=24, blank=True)
    plate_emirate = models.CharField(max_length=32, blank=True)
    make = models.CharField(max_length=64, blank=True)
    model = models.CharField(max_length=64, blank=True)
    model_year = models.PositiveSmallIntegerField(null=True, blank=True)
    vin = models.CharField(max_length=32, blank=True)
    ownership = models.CharField(max_length=12, choices=Ownership.choices, default=Ownership.OWNED)
    acquisition_date = models.DateField(null=True, blank=True)
    acquisition_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    residual_value = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    useful_life_months = models.PositiveSmallIntegerField(null=True, blank=True)
    asset_account = models.ForeignKey(
        "accounts.Account", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    depreciation_expense_account = models.ForeignKey(
        "accounts.Account", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    accumulated_depreciation_account = models.ForeignKey(
        "accounts.Account", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["entity", "code"]
        constraints = [
            models.UniqueConstraint(fields=["entity", "code"], name="fleet_vehicle_unique_code"),
        ]

    def __str__(self):
        return f"{self.code} {self.plate_no}".strip()

    @property
    def monthly_depreciation(self):
        """Straight-line monthly depreciation (0 if not configured)."""
        if not self.useful_life_months:
            return Decimal("0.00")
        base = Decimal(self.acquisition_cost) - Decimal(self.residual_value)
        if base <= 0:
            return Decimal("0.00")
        return (base / Decimal(self.useful_life_months)).quantize(
            TWO_PLACES, rounding=ROUND_HALF_UP
        )


class VehicleDocument(BaseModel):
    """A renewable vehicle document (Mulkiya, insurance, Salik tag, etc.)."""

    class DocType(models.TextChoices):
        REGISTRATION = "registration", "Registration / Mulkiya"
        INSURANCE = "insurance", "Insurance"
        SALIK_TAG = "salik_tag", "Salik Tag"
        PERMIT = "permit", "Permit"
        OTHER = "other", "Other"

    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name="documents")
    doc_type = models.CharField(max_length=16, choices=DocType.choices)
    doc_no = models.CharField(max_length=64, blank=True)
    issue_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True, db_index=True)
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["vehicle", "expiry_date"]

    def __str__(self):
        return f"{self.vehicle_id} {self.doc_type} exp {self.expiry_date}"

    def days_to_expiry(self, as_of=None):
        if not self.expiry_date:
            return None
        return (self.expiry_date - (as_of or date.today())).days


class AmortizationMethod(models.TextChoices):
    """How an EMI schedule splits principal vs interest.

    ``LENDER_PROVIDED`` is a deliberate extension point: a bank's actual schedule
    can differ from a mathematically generated one (day counts, fees, grace
    periods, rescheduling, lender rounding). When that lands, schedules will be
    imported rather than computed — the generator must not be forced to
    approximate them.
    """

    REDUCING_BALANCE = "reducing_balance", "Reducing balance"
    FLAT_RATE = "flat_rate", "Flat rate"


class VehicleLoan(BaseModel):
    """A finance loan against a vehicle; installments post EMI splits.

    The lender's approved repayment schedule is the authoritative source — the
    generated :class:`LoanSchedule` models it, and is versioned so an amendment
    never rewrites what was already posted.
    """

    entity = models.ForeignKey(
        "tenants.Entity", on_delete=models.PROTECT, related_name="vehicle_loans"
    )
    vehicle = models.ForeignKey(Vehicle, on_delete=models.PROTECT, related_name="loans")
    lender = models.CharField(max_length=128, blank=True)
    loan_account = models.ForeignKey(
        "accounts.Account", on_delete=models.PROTECT, related_name="+"
    )  # liability
    interest_account = models.ForeignKey(
        "accounts.Account", on_delete=models.PROTECT, related_name="+"
    )  # finance cost
    principal = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    down_payment = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    term_months = models.PositiveSmallIntegerField(null=True, blank=True)
    emi_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    annual_interest_rate = models.DecimalField(max_digits=6, decimal_places=3, default=0)
    amortization_method = models.CharField(
        max_length=20,
        choices=AmortizationMethod.choices,
        default=AmortizationMethod.REDUCING_BALANCE,
    )
    # Rates are stored separately: UAE auto finance is commonly *quoted* flat while
    # the effective annual rate differs. Neither is derived from the other here.
    quoted_flat_rate = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True)
    effective_annual_rate = models.DecimalField(
        max_digits=6, decimal_places=3, null=True, blank=True
    )
    start_date = models.DateField(null=True, blank=True)
    first_payment_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["entity", "-start_date"]

    def __str__(self):
        return f"Loan {self.vehicle_id} {self.principal}"


class LoanSchedule(BaseModel):
    """One generated amortization schedule version for a loan.

    Schedules are generated as ``DRAFT``, validated to reconcile exactly, then
    ``APPROVED`` — which locks them. Regenerating produces a **new version** and
    supersedes the previous one; posted installments are never rewritten.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        APPROVED = "approved", "Approved"
        SUPERSEDED = "superseded", "Superseded"

    loan = models.ForeignKey(VehicleLoan, on_delete=models.PROTECT, related_name="schedules")
    version_no = models.PositiveSmallIntegerField(default=1)
    method = models.CharField(max_length=20, choices=AmortizationMethod.choices)
    # Snapshot of the inputs this version was generated from (auditable).
    opening_principal = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    annual_interest_rate = models.DecimalField(max_digits=6, decimal_places=3, default=0)
    term_months = models.PositiveSmallIntegerField(default=0)
    first_payment_date = models.DateField()
    total_principal = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    total_interest = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    total_payments = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.DRAFT, db_index=True
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["loan", "-version_no"]
        constraints = [
            models.UniqueConstraint(
                fields=["loan", "version_no"], name="fleet_loan_schedule_unique_version"
            ),
        ]

    def __str__(self):
        return f"Schedule v{self.version_no} {self.loan_id} [{self.status}]"


class VehicleLoanInstallment(BaseModel):
    """One EMI. Posting: DR Loan Payable (principal) / DR Interest / CR Bank (total).

    Belongs to a :class:`LoanSchedule` version (``schedule`` is null only for rows
    created before schedules existed). Once posted an installment is immutable —
    regenerating a schedule must never rewrite it.
    """

    loan = models.ForeignKey(VehicleLoan, on_delete=models.CASCADE, related_name="installments")
    schedule = models.ForeignKey(
        LoanSchedule, on_delete=models.CASCADE, null=True, blank=True, related_name="installments"
    )
    installment_no = models.PositiveSmallIntegerField(default=0)
    due_date = models.DateField(db_index=True)
    principal_component = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    interest_component = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    opening_balance = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    closing_balance = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    bank_account = models.ForeignKey(
        "banking.BankAccount", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    status = models.CharField(
        max_length=12, choices=FleetDocStatus.choices, default=FleetDocStatus.DRAFT, db_index=True
    )
    journal_entry = models.ForeignKey(
        "ledger.JournalEntry", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )

    class Meta:
        ordering = ["loan", "installment_no"]
        constraints = [
            # Scoped to the schedule version, so a superseded version's rows can
            # coexist with the new version's. (Legacy rows have schedule=NULL.)
            models.UniqueConstraint(
                fields=["schedule", "installment_no"],
                name="fleet_loan_installment_unique_in_schedule",
            ),
        ]

    def __str__(self):
        return f"EMI {self.loan_id}#{self.installment_no} {self.total_amount}"


class DepreciationRun(BaseModel):
    """A periodic depreciation run; one JE with a line pair per vehicle."""

    entity = models.ForeignKey(
        "tenants.Entity", on_delete=models.PROTECT, related_name="depreciation_runs"
    )
    run_no = models.CharField(max_length=24, blank=True)
    run_date = models.DateField(db_index=True)
    period_label = models.CharField(max_length=32, blank=True)
    total_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    status = models.CharField(
        max_length=12, choices=FleetDocStatus.choices, default=FleetDocStatus.DRAFT, db_index=True
    )
    journal_entry = models.ForeignKey(
        "ledger.JournalEntry", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )

    class Meta:
        ordering = ["-run_date", "-created_at"]

    def __str__(self):
        return f"DepRun {self.run_no or '(draft)'} {self.run_date}"


class DepreciationLine(BaseModel):
    run = models.ForeignKey(DepreciationRun, on_delete=models.CASCADE, related_name="lines")
    vehicle = models.ForeignKey(
        Vehicle, on_delete=models.PROTECT, related_name="depreciation_lines"
    )
    amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    class Meta:
        ordering = ["run", "vehicle"]

    def __str__(self):
        return f"{self.vehicle_id} {self.amount}"
