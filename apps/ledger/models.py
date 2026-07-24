"""General ledger: accounting periods, journal entries, journal lines (doc 02).

The posting engine in ``services/posting.py`` is the ONLY writer that moves an
entry to ``posted``. Once posted, an entry and its lines are immutable
(enforced here in ``save``/``delete`` plus the service); corrections happen by
reversal. See ADR-0007.
"""

from django.conf import settings
from django.db import models

from apps.core.models import BaseModel

TERMINAL_STATUSES = {"posted", "reversed", "cancelled"}


class EntryStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    VALIDATED = "validated", "Validated"
    POSTED = "posted", "Posted"
    REVERSED = "reversed", "Reversed"
    CANCELLED = "cancelled", "Cancelled"


class AccountingPeriod(BaseModel):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        CLOSED = "closed", "Closed"
        LOCKED = "locked", "Locked"

    entity = models.ForeignKey("tenants.Entity", on_delete=models.PROTECT, related_name="periods")
    fiscal_year = models.PositiveSmallIntegerField()
    period_no = models.PositiveSmallIntegerField()
    name = models.CharField(max_length=32)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.OPEN)
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        ordering = ["entity", "fiscal_year", "period_no"]
        constraints = [
            models.UniqueConstraint(
                fields=["entity", "fiscal_year", "period_no"],
                name="ledger_period_unique",
            ),
        ]

    def __str__(self):
        return f"{self.name} [{self.status}]"

    @property
    def is_open(self):
        return self.status == self.Status.OPEN


class JournalEntry(BaseModel):
    class Basis(models.TextChoices):
        ACCRUAL = "accrual", "Accrual"
        CASH = "cash", "Cash"

    entity = models.ForeignKey(
        "tenants.Entity", on_delete=models.PROTECT, related_name="journal_entries"
    )
    branch = models.ForeignKey(
        "tenants.Branch", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    period = models.ForeignKey(
        AccountingPeriod, on_delete=models.PROTECT, null=True, blank=True, related_name="entries"
    )
    entry_no = models.CharField(max_length=24, blank=True)  # assigned at post
    entry_date = models.DateField(db_index=True)
    basis = models.CharField(max_length=8, choices=Basis.choices, default=Basis.ACCRUAL)
    source_type = models.CharField(max_length=16, default="manual", db_index=True)
    source_id = models.UUIDField(null=True, blank=True, db_index=True)
    narration = models.CharField(max_length=512, blank=True)
    currency = models.ForeignKey(
        "core.Currency", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    total_debit = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    total_credit = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    status = models.CharField(
        max_length=12, choices=EntryStatus.choices, default=EntryStatus.DRAFT, db_index=True
    )
    reversal_of = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="reversals"
    )
    reversed_by = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    posted_at = models.DateTimeField(null=True, blank=True)
    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        ordering = ["-entry_date", "-created_at"]
        indexes = [
            models.Index(fields=["entity", "entry_date"]),
            models.Index(fields=["source_type", "source_id"]),
        ]

    def __str__(self):
        return f"JE {self.entry_no or '(draft)'} {self.entry_date} [{self.status}]"

    def save(self, *args, **kwargs):
        # Posted/terminal entries are immutable except via the posting/reversal
        # service, which sets ``_system_update`` for its controlled writes. The
        # flag is consumed (reset) after one save so it cannot leak on the instance.
        system_update = getattr(self, "_system_update", False)
        if self.pk and not system_update:
            old_status = (
                type(self).all_objects.filter(pk=self.pk).values_list("status", flat=True).first()
            )
            if old_status in TERMINAL_STATUSES:
                raise ValueError(
                    f"Journal entry {self.pk} is {old_status} and cannot be modified "
                    "(use a reversal)."
                )
        super().save(*args, **kwargs)
        self._system_update = False

    def delete(self, *args, **kwargs):
        if self.status in TERMINAL_STATUSES:
            raise ValueError(f"A {self.status} journal entry cannot be deleted (use a reversal).")
        return super().delete(*args, **kwargs)


class JournalLine(BaseModel):
    entry = models.ForeignKey(JournalEntry, on_delete=models.CASCADE, related_name="lines")
    line_no = models.PositiveSmallIntegerField(default=0)
    account = models.ForeignKey("accounts.Account", on_delete=models.PROTECT, related_name="+")
    description = models.CharField(max_length=512, blank=True)
    debit = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    credit = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    fx_rate = models.DecimalField(max_digits=18, decimal_places=6, default=1)
    base_debit = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    base_credit = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    cost_center = models.ForeignKey(
        "tenants.CostCenter", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    # Subledger party (polymorphic): customer / supplier. FKs land with ar/ap.
    party_type = models.CharField(max_length=12, blank=True)
    party_id = models.UUIDField(null=True, blank=True, db_index=True)
    # Profitability dimensions. Become FKs when fleet/drivers/platforms are built.
    vehicle_id = models.UUIDField(null=True, blank=True, db_index=True)
    driver_id = models.UUIDField(null=True, blank=True, db_index=True)
    platform_id = models.UUIDField(null=True, blank=True, db_index=True)
    tax_code = models.ForeignKey(
        "accounts.TaxCode", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    tax_amount = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ["entry", "line_no"]

    def __str__(self):
        return f"{self.account_id} D{self.debit}/C{self.credit}"

    def save(self, *args, **kwargs):
        system_update = getattr(self, "_system_update", False)
        if self.entry_id and not system_update:
            status = (
                JournalEntry.all_objects.filter(pk=self.entry_id)
                .values_list("status", flat=True)
                .first()
            )
            if status in TERMINAL_STATUSES:
                raise ValueError("Cannot modify lines of a posted journal entry.")
        super().save(*args, **kwargs)
        self._system_update = False

    def delete(self, *args, **kwargs):
        status = (
            JournalEntry.all_objects.filter(pk=self.entry_id)
            .values_list("status", flat=True)
            .first()
        )
        if status in TERMINAL_STATUSES:
            raise ValueError("Cannot delete lines of a posted journal entry.")
        return super().delete(*args, **kwargs)
