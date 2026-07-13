"""Reporting layer (design doc 05).

Reports are DERIVED from the ledger — never stored as balances. These tables hold
only (a) statement templates that map the COA onto each statement's layout, (b)
optional period-end snapshots for dashboard performance (derived, never a source of
truth), and (c) the report run log + schedule that drive generated/recurring output.
"""

from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class StatementTemplate(BaseModel):
    """Structure of a statement (TB/PNL/BS/CF). Group default when entity is null."""

    entity = models.ForeignKey(
        "tenants.Entity",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="statement_templates",
    )
    code = models.CharField(max_length=16)  # PNL / BS / CF / TB
    name = models.CharField(max_length=128)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["entity", "code"]
        constraints = [
            models.UniqueConstraint(fields=["entity", "code"], name="reports_template_unique_code"),
        ]

    def __str__(self):
        return f"{self.code} {self.name}"


class StatementLine(BaseModel):
    """Ordered, hierarchical line of a template, mapped to COA segment ranges."""

    class LineType(models.TextChoices):
        HEADER = "header", "Header"
        RANGE = "range", "Range"
        SUBTOTAL = "subtotal", "Subtotal"
        TOTAL = "total", "Total"
        FORMULA = "formula", "Formula"

    template = models.ForeignKey(StatementTemplate, on_delete=models.CASCADE, related_name="lines")
    line_no = models.PositiveSmallIntegerField()
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="children"
    )
    label = models.CharField(max_length=128)
    line_type = models.CharField(max_length=16, choices=LineType.choices)
    main_from = models.CharField(max_length=3, blank=True)
    main_to = models.CharField(max_length=3, blank=True)
    sub_from = models.CharField(max_length=3, blank=True)
    sub_to = models.CharField(max_length=3, blank=True)
    sign = models.SmallIntegerField(default=1)  # +1 / -1 presentation
    formula = models.CharField(max_length=255, blank=True)  # refs other line_no
    indent = models.SmallIntegerField(default=0)
    is_bold = models.BooleanField(default=False)

    class Meta:
        ordering = ["template", "line_no"]

    def __str__(self):
        return f"{self.template_id}#{self.line_no} {self.label}"


class BalanceSnapshot(BaseModel):
    """Optional period-end balances per account (performance). Derived."""

    entity = models.ForeignKey(
        "tenants.Entity", on_delete=models.PROTECT, related_name="balance_snapshots"
    )
    period = models.ForeignKey(
        "ledger.AccountingPeriod", on_delete=models.PROTECT, related_name="+"
    )
    account = models.ForeignKey("accounts.Account", on_delete=models.PROTECT, related_name="+")
    opening_debit = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    opening_credit = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    period_debit = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    period_credit = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    closing_balance = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    class Meta:
        ordering = ["entity", "period", "account"]
        constraints = [
            models.UniqueConstraint(
                fields=["entity", "period", "account"], name="reports_balance_snapshot_unique"
            ),
        ]

    def __str__(self):
        return f"{self.account_id} {self.closing_balance}"


class ProfitSnapshot(BaseModel):
    """Optional per-dimension profitability (performance, doc 04). Derived."""

    entity = models.ForeignKey(
        "tenants.Entity", on_delete=models.PROTECT, related_name="profit_snapshots"
    )
    dim_type = models.CharField(
        max_length=16
    )  # vehicle/driver/platform/customer/branch/cost_center
    dim_id = models.UUIDField(db_index=True)
    period = models.ForeignKey(
        "ledger.AccountingPeriod", on_delete=models.PROTECT, related_name="+"
    )
    revenue = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    direct_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    overhead = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    net_profit = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    class Meta:
        ordering = ["entity", "dim_type", "dim_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["entity", "dim_type", "dim_id", "period"],
                name="reports_profit_snapshot_unique",
            ),
        ]

    def __str__(self):
        return f"{self.dim_type}:{self.dim_id} {self.net_profit}"


class ReportRun(BaseModel):
    """Audit log of every generated report (who/what/when + produced file)."""

    class Scope(models.TextChoices):
        ENTITY = "entity", "Entity"
        GROUP = "group", "Group"

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        DONE = "done", "Done"
        ERROR = "error", "Error"

    entity_scope = models.CharField(max_length=8, choices=Scope.choices, default=Scope.ENTITY)
    entity = models.ForeignKey(
        "tenants.Entity", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    report_code = models.CharField(max_length=24, db_index=True)
    params = models.JSONField(default=dict)
    format = models.CharField(max_length=8, default="json")  # xlsx / pdf / json
    file_ref = models.CharField(max_length=512, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.QUEUED)
    generated_at = models.DateTimeField(null=True, blank=True)
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.report_code} [{self.status}]"


class ReportSchedule(BaseModel):
    """Recurring MIS schedule (driven by Celery)."""

    name = models.CharField(max_length=128)
    report_code = models.CharField(max_length=24)
    entity_scope = models.CharField(
        max_length=8, choices=ReportRun.Scope.choices, default=ReportRun.Scope.ENTITY
    )
    entity = models.ForeignKey(
        "tenants.Entity", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    params = models.JSONField(default=dict)
    cron = models.CharField(max_length=32)
    format = models.CharField(max_length=8, default="xlsx")
    recipients = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.report_code})"
