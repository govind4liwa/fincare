"""Bookings module (design doc 04 §bookings).

The trip register is the operational grain that rolls up into revenue and
profitability. Platform trips are imported & aggregated; personal/corporate trips
entered directly. Revenue is recognised by **periodic aggregate posting** grouped by
platform/vehicle/driver (not one JE per trip), with lines carrying the vehicle/driver/
platform dimensions. Contracts generate a scheduled ``ar.SalesInvoice`` each cycle.
All money posts through the ledger engine (ADR-0007).
"""

from django.db import models

from apps.core.models import BaseModel


class TripType(models.TextChoices):
    PLATFORM = "platform", "Platform"
    PERSONAL = "personal", "Personal"
    CORPORATE = "corporate", "Corporate"
    CONTRACT = "contract", "Contract"


class TripStatus(models.TextChoices):
    RECORDED = "recorded", "Recorded"
    INVOICED = "invoiced", "Invoiced"  # revenue recognised (aggregate posted)
    SETTLED = "settled", "Settled"  # platform paid


class Trip(BaseModel):
    """A single trip. Profitability dims (vehicle/driver/platform/customer) roll up
    into the periodic aggregate revenue posting."""

    entity = models.ForeignKey("tenants.Entity", on_delete=models.PROTECT, related_name="trips")
    trip_date = models.DateField(db_index=True)
    trip_type = models.CharField(max_length=16, choices=TripType.choices)
    vehicle = models.ForeignKey(
        "fleet.Vehicle", on_delete=models.PROTECT, null=True, blank=True, related_name="trips"
    )
    driver = models.ForeignKey(
        "drivers.Driver", on_delete=models.PROTECT, null=True, blank=True, related_name="trips"
    )
    platform = models.ForeignKey(
        "platforms.Platform", on_delete=models.PROTECT, null=True, blank=True, related_name="trips"
    )
    customer = models.ForeignKey(
        "ar.Customer", on_delete=models.PROTECT, null=True, blank=True, related_name="trips"
    )
    fare = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    commission = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    salik = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    tip = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    distance_km = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    net_revenue = models.DecimalField(
        max_digits=18, decimal_places=2, default=0
    )  # fare - commission
    status = models.CharField(
        max_length=12, choices=TripStatus.choices, default=TripStatus.RECORDED, db_index=True
    )
    revenue_journal_entry = models.ForeignKey(
        "ledger.JournalEntry", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )

    class Meta:
        ordering = ["-trip_date", "-created_at"]
        indexes = [
            models.Index(fields=["entity", "platform", "trip_date"]),
            models.Index(fields=["entity", "status"]),
        ]

    def __str__(self):
        return f"Trip {self.trip_date} {self.trip_type} {self.fare}"

    def compute_net(self):
        self.net_revenue = self.fare - self.commission
        return self.net_revenue


class Contract(BaseModel):
    """Monthly corporate/contract billing agreement → scheduled ar.SalesInvoice."""

    class Cycle(models.TextChoices):
        MONTHLY = "monthly", "Monthly"
        WEEKLY = "weekly", "Weekly"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        ENDED = "ended", "Ended"

    entity = models.ForeignKey("tenants.Entity", on_delete=models.PROTECT, related_name="contracts")
    customer = models.ForeignKey("ar.Customer", on_delete=models.PROTECT, related_name="contracts")
    vehicle = models.ForeignKey(
        "fleet.Vehicle", on_delete=models.PROTECT, null=True, blank=True, related_name="contracts"
    )
    driver = models.ForeignKey(
        "drivers.Driver", on_delete=models.PROTECT, null=True, blank=True, related_name="contracts"
    )
    contract_no = models.CharField(max_length=24)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    billing_cycle = models.CharField(max_length=12, choices=Cycle.choices, default=Cycle.MONTHLY)
    monthly_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    revenue_account = models.ForeignKey(
        "accounts.Account", on_delete=models.PROTECT, related_name="+"
    )
    tax_code = models.ForeignKey("accounts.TaxCode", on_delete=models.PROTECT, related_name="+")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ACTIVE)

    class Meta:
        ordering = ["entity", "contract_no"]
        constraints = [
            models.UniqueConstraint(
                fields=["entity", "contract_no"], name="bookings_contract_unique_no"
            ),
        ]

    def __str__(self):
        return f"Contract {self.contract_no} {self.customer_id}"
