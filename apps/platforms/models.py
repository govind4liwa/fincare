"""Platforms module (design doc 04 §platforms).

Ride-hailing / aggregator platforms (Uber, Yango, Bolt, Careem, ...). Each platform
maps to its own revenue, commission and clearing GL accounts. Trip revenue accrues a
receivable into the platform clearing account (see ``bookings``); a ``Settlement``
reconciles the platform's statement against that clearing balance, routes any
variance to an adjustment account, and posts the bank receipt — all through the
ledger engine (ADR-0007). A platform's id is the ``platform_id`` profitability
dimension carried on journal lines.
"""

from django.db import models

from apps.core.models import BaseModel


class PlatformDocStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    RECONCILED = "reconciled", "Reconciled"
    POSTED = "posted", "Posted"
    REVERSED = "reversed", "Reversed"


class Platform(BaseModel):
    """A ride-hailing / aggregator platform. Its id is the ``platform_id`` dim."""

    class Cycle(models.TextChoices):
        DAILY = "daily", "Daily"
        WEEKLY = "weekly", "Weekly"
        MONTHLY = "monthly", "Monthly"

    entity = models.ForeignKey("tenants.Entity", on_delete=models.PROTECT, related_name="platforms")
    name = models.CharField(max_length=64)
    commission_pct = models.DecimalField(max_digits=6, decimal_places=3, default=0)  # config
    settlement_cycle = models.CharField(max_length=12, choices=Cycle.choices, blank=True)
    revenue_account = models.ForeignKey(
        "accounts.Account", on_delete=models.PROTECT, related_name="+"
    )  # 400-410 platform earnings
    commission_account = models.ForeignKey(
        "accounts.Account", on_delete=models.PROTECT, related_name="+"
    )  # 500-520 platform commission
    clearing_account = models.ForeignKey(
        "accounts.Account", on_delete=models.PROTECT, related_name="+"
    )  # 100-110 platform settlement clearing (receivable)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["entity", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["entity", "name"], name="platforms_platform_unique_name"
            ),
        ]

    def __str__(self):
        return self.name


class PlatformSettlement(BaseModel):
    """Reconciles a platform statement against the clearing account.

    Trip postings leave a debit (receivable) in the platform clearing account.
    When the platform pays, this settlement clears that balance against the bank
    receipt and books the difference to an adjustment account. Posting:
        DR  Bank                         = net_received
        CR  Platform Clearing            = gross_earnings − commission
        CR/DR Adjustment account         = net_received − clearing  (signed)
    """

    entity = models.ForeignKey(
        "tenants.Entity", on_delete=models.PROTECT, related_name="platform_settlements"
    )
    platform = models.ForeignKey(Platform, on_delete=models.PROTECT, related_name="settlements")
    settlement_no = models.CharField(max_length=24, blank=True)
    period_start = models.DateField()
    period_end = models.DateField()
    settlement_date = models.DateField(db_index=True)
    gross_earnings = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    commission = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    adjustments = models.DecimalField(max_digits=18, decimal_places=2, default=0)  # tips/incentives
    net_received = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    variance = models.DecimalField(max_digits=18, decimal_places=2, default=0)  # unexplained
    bank_account = models.ForeignKey(
        "banking.BankAccount", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    adjustment_account = models.ForeignKey(
        "accounts.Account", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    status = models.CharField(
        max_length=12,
        choices=PlatformDocStatus.choices,
        default=PlatformDocStatus.DRAFT,
        db_index=True,
    )
    journal_entry = models.ForeignKey(
        "ledger.JournalEntry", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )

    class Meta:
        ordering = ["-settlement_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["entity", "platform", "period_start", "period_end"],
                name="platforms_settlement_unique_period",
            ),
        ]

    def __str__(self):
        return f"SETTLE {self.settlement_no or '(draft)'} {self.platform_id}"


class EarningImport(BaseModel):
    """Raw imported statement line (CSV/API), staged before reconciliation."""

    entity = models.ForeignKey(
        "tenants.Entity", on_delete=models.PROTECT, related_name="platform_earning_imports"
    )
    platform = models.ForeignKey(Platform, on_delete=models.PROTECT, related_name="earning_imports")
    settlement = models.ForeignKey(
        PlatformSettlement,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="earning_imports",
    )
    trip_ref = models.CharField(max_length=64, blank=True)
    driver_ref = models.CharField(max_length=64, blank=True)
    earning_date = models.DateField(db_index=True)
    gross = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    commission = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    net = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    matched = models.BooleanField(default=False)

    class Meta:
        ordering = ["platform", "earning_date"]

    def __str__(self):
        return f"{self.platform_id} {self.trip_ref} {self.net}"
