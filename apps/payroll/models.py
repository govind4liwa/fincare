"""Payroll module (design doc 07).

Monthly payroll for all employees (admin staff and salaried drivers): salary
structures, runs/payslips, UAE WPS (Wage Protection System) SIF generation,
end-of-service gratuity (EOSB), leave accrual, and salary advances. All money posts
through the ledger engine (ADR-0007): a run produces one accrual entry; the WPS
salary payment is a separate entry.

Driver/payroll boundary (doc 07 §boundary): a salaried driver is paid once, through
payroll (``Employee.driver`` links to the fleet driver); pure commission drivers are
paid only via ``drivers.Settlement``. UAE statutory figures (gratuity day-rates, WPS
routing, SIF layout) are configuration (``settings``), never hardcoded.
"""

from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class ComponentType(models.TextChoices):
    EARNING = "earning", "Earning"
    DEDUCTION = "deduction", "Deduction"


class RunStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    APPROVED = "approved", "Approved"
    POSTED = "posted", "Posted"
    PAID = "paid", "Paid"


class PayslipStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    FINALISED = "finalised", "Finalised"
    PAID = "paid", "Paid"


class Employee(BaseModel):
    class PayMethod(models.TextChoices):
        WPS = "wps", "WPS"
        BANK = "bank", "Bank transfer"
        CASH = "cash", "Cash"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        ON_LEAVE = "on_leave", "On leave"
        LEFT = "left", "Left"

    entity = models.ForeignKey("tenants.Entity", on_delete=models.PROTECT, related_name="employees")
    code = models.CharField(max_length=24)
    name = models.CharField(max_length=255)
    driver = models.ForeignKey(
        "drivers.Driver", on_delete=models.SET_NULL, null=True, blank=True, related_name="employees"
    )
    emirates_id = models.CharField(max_length=32, blank=True)
    passport_no = models.CharField(max_length=32, blank=True)
    nationality = models.CharField(max_length=64, blank=True)
    join_date = models.DateField()
    designation = models.CharField(max_length=128, blank=True)
    department = models.ForeignKey(
        "tenants.Department", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    branch = models.ForeignKey(
        "tenants.Branch", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    mol_personal_no = models.CharField(max_length=32, blank=True)  # MOHRE labour card (WPS)
    work_permit_no = models.CharField(max_length=32, blank=True)
    pay_method = models.CharField(max_length=12, choices=PayMethod.choices, default=PayMethod.WPS)
    bank_routing_code = models.CharField(max_length=16, blank=True)
    iban = models.CharField(max_length=34, blank=True)
    payable_account = models.ForeignKey(
        "accounts.Account", on_delete=models.PROTECT, related_name="+"
    )  # 240 Salaries Payable / WPS clearing
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.ACTIVE, db_index=True
    )
    left_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["entity", "code"]
        constraints = [
            models.UniqueConstraint(fields=["entity", "code"], name="payroll_employee_unique_code"),
        ]

    def __str__(self):
        return f"{self.code} {self.name}"


class SalaryComponent(BaseModel):
    """Master earning/deduction component (config). Entity-null = group default."""

    entity = models.ForeignKey(
        "tenants.Entity",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="salary_components",
    )
    code = models.CharField(max_length=24)  # BASIC, HRA, TRANSPORT, ADV, ...
    name = models.CharField(max_length=128)
    component_type = models.CharField(max_length=12, choices=ComponentType.choices)
    is_gratuity_base = models.BooleanField(default=False)  # counts toward EOSB (usually BASIC)
    is_wps_fixed = models.BooleanField(default=True)  # fixed vs variable for SIF split
    account = models.ForeignKey(
        "accounts.Account", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )  # earnings: salary expense (DR); deductions: credit account (CR)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["entity", "code"]
        constraints = [
            models.UniqueConstraint(
                fields=["entity", "code"], name="payroll_component_unique_code"
            ),
        ]

    def __str__(self):
        return f"{self.code} {self.name}"


class EmployeeSalary(BaseModel):
    """Effective-dated salary structure (one row per component version)."""

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="salary")
    component = models.ForeignKey(SalaryComponent, on_delete=models.PROTECT, related_name="+")
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)  # null = current

    class Meta:
        ordering = ["employee", "component", "-effective_from"]

    def __str__(self):
        return f"{self.employee_id} {self.component_id} {self.amount}"


class Run(BaseModel):
    """Monthly payroll batch per entity + period."""

    entity = models.ForeignKey(
        "tenants.Entity", on_delete=models.PROTECT, related_name="payroll_runs"
    )
    period = models.ForeignKey(
        "ledger.AccountingPeriod", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    salary_month = models.CharField(max_length=7)  # "2026-06"
    run_date = models.DateField(db_index=True)
    gross_total = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    deduction_total = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    net_total = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    status = models.CharField(
        max_length=12, choices=RunStatus.choices, default=RunStatus.DRAFT, db_index=True
    )
    journal_entry = models.ForeignKey(
        "ledger.JournalEntry", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )  # accrual posting
    payment_entry = models.ForeignKey(
        "ledger.JournalEntry", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )  # WPS / bank payment posting
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        ordering = ["-salary_month", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["entity", "salary_month"], name="payroll_run_unique_month"
            ),
        ]

    def __str__(self):
        return f"Payroll {self.salary_month} [{self.status}]"


class Payslip(BaseModel):
    run = models.ForeignKey(Run, on_delete=models.CASCADE, related_name="payslips")
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="payslips")
    working_days = models.DecimalField(max_digits=6, decimal_places=2, default=30)
    lop_days = models.DecimalField(max_digits=6, decimal_places=2, default=0)  # loss of pay
    gross_earnings = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    total_deductions = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    advance_recovery = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    net_pay = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    status = models.CharField(
        max_length=12, choices=PayslipStatus.choices, default=PayslipStatus.DRAFT
    )

    class Meta:
        ordering = ["run", "employee"]
        constraints = [
            models.UniqueConstraint(
                fields=["run", "employee"], name="payroll_payslip_unique_employee"
            ),
        ]

    def __str__(self):
        return f"Payslip {self.employee_id} net={self.net_pay}"


class PayslipLine(BaseModel):
    payslip = models.ForeignKey(Payslip, on_delete=models.CASCADE, related_name="lines")
    component = models.ForeignKey(SalaryComponent, on_delete=models.PROTECT, related_name="+")
    component_type = models.CharField(max_length=12, choices=ComponentType.choices)
    amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    class Meta:
        ordering = ["payslip", "component_type", "component"]

    def __str__(self):
        return f"{self.component_id} {self.component_type} {self.amount}"


class WpsBatch(BaseModel):
    """Salary Control Record (employer header) for a WPS SIF file."""

    class Status(models.TextChoices):
        GENERATED = "generated", "Generated"
        SUBMITTED = "submitted", "Submitted"

    run = models.ForeignKey(Run, on_delete=models.CASCADE, related_name="wps_batches")
    employer_eid = models.CharField(max_length=32)  # MOHRE establishment ID
    employer_bank_routing = models.CharField(max_length=16)
    salary_month = models.CharField(max_length=7)
    total_records = models.PositiveIntegerField(default=0)
    total_salary = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    fixed_total = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    variable_total = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    sif_file_ref = models.CharField(max_length=512, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.GENERATED)
    generated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"WPS {self.salary_month} ({self.total_records} recs)"


class WpsRecord(BaseModel):
    """Employee Detail Record within a WPS SIF file."""

    batch = models.ForeignKey(WpsBatch, on_delete=models.CASCADE, related_name="records")
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="+")
    mol_personal_no = models.CharField(max_length=32)
    bank_routing_code = models.CharField(max_length=16)
    iban = models.CharField(max_length=34)
    pay_start_date = models.DateField()
    pay_end_date = models.DateField()
    working_days = models.DecimalField(max_digits=6, decimal_places=2, default=30)
    fixed_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    variable_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    leave_days = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["batch", "employee"]

    def __str__(self):
        return f"EDR {self.employee_id} {self.fixed_amount}+{self.variable_amount}"


class Gratuity(BaseModel):
    """End-of-service benefit accrual / settlement (EOSB)."""

    class Type(models.TextChoices):
        ACCRUAL = "accrual", "Accrual"
        SETTLEMENT = "settlement", "Settlement"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        POSTED = "posted", "Posted"
        SETTLED = "settled", "Settled"

    entity = models.ForeignKey(
        "tenants.Entity", on_delete=models.PROTECT, related_name="gratuities"
    )
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="gratuities")
    as_of_date = models.DateField()
    service_years = models.DecimalField(max_digits=8, decimal_places=4, default=0)
    basis_salary = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    eligible_days = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    type = models.CharField(max_length=12, choices=Type.choices, default=Type.ACCRUAL)
    provision_account = models.ForeignKey(
        "accounts.Account", on_delete=models.PROTECT, related_name="+"
    )
    expense_account = models.ForeignKey(
        "accounts.Account", on_delete=models.PROTECT, related_name="+"
    )
    bank_account = models.ForeignKey(
        "banking.BankAccount", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    journal_entry = models.ForeignKey(
        "ledger.JournalEntry", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)

    class Meta:
        ordering = ["-as_of_date", "-created_at"]

    def __str__(self):
        return f"Gratuity {self.employee_id} {self.type} {self.amount}"


class Leave(BaseModel):
    """Leave balance + leave-salary accrual per employee."""

    class LeaveType(models.TextChoices):
        ANNUAL = "annual", "Annual"
        SICK = "sick", "Sick"
        UNPAID = "unpaid", "Unpaid"

    entity = models.ForeignKey("tenants.Entity", on_delete=models.PROTECT, related_name="leaves")
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="leaves")
    leave_type = models.CharField(max_length=16, choices=LeaveType.choices)
    entitled_days = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    taken_days = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    balance_days = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    accrued_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    provision_account = models.ForeignKey(
        "accounts.Account", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    expense_account = models.ForeignKey(
        "accounts.Account", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    journal_entry = models.ForeignKey(
        "ledger.JournalEntry", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    as_of_date = models.DateField()

    class Meta:
        ordering = ["-as_of_date", "-created_at"]

    def __str__(self):
        return f"Leave {self.employee_id} {self.leave_type} bal={self.balance_days}"


class Advance(BaseModel):
    """Salary advance / loan, recovered via payslips."""

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        RECOVERING = "recovering", "Recovering"
        CLEARED = "cleared", "Cleared"

    entity = models.ForeignKey(
        "tenants.Entity", on_delete=models.PROTECT, related_name="payroll_advances"
    )
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="advances")
    advance_date = models.DateField()
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    installments = models.PositiveSmallIntegerField(default=1)
    installment_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    recovered_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    balance = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    advance_account = models.ForeignKey(
        "accounts.Account", on_delete=models.PROTECT, related_name="+"
    )  # Staff Advances (120)
    bank_account = models.ForeignKey(
        "banking.BankAccount", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    journal_entry = models.ForeignKey(
        "ledger.JournalEntry", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.OPEN)

    class Meta:
        ordering = ["-advance_date", "-created_at"]

    def __str__(self):
        return f"Salary advance {self.employee_id} {self.amount}"
