"""Tax module: UAE VAT (FTA VAT 201) and Corporate Tax (design doc 03 §tax).

VAT returns are filed per **VAT group** (one shared TRN across member entities,
ADR-0006) or per standalone entity. The return aggregates VAT across all member
entities for a filing period. The authoritative VAT figures are derived from the
**VAT control accounts** in the general ledger (accounts of type ``vat_output`` /
``vat_input``) — the return always ties to the GL. The VAT 201 box breakdown
(emirate split of standard-rated supplies) is supplementary detail sourced from
the sales subledger. See ``services/vat.py``.

Corporate Tax is filed per **entity** per fiscal year (separate TRN, not grouped).

Effective-dated VAT rates live in ``TaxCodeRateHistory`` so a rate change (e.g. a
future FTA rate revision) never mutates posted history — rates are config-driven,
never hardcoded.
"""

from django.conf import settings
from django.db import models

from apps.core.models import BaseModel

# UAE emirates for the VAT 201 standard-rated supplies split (Box 1a–1g).
EMIRATES = [
    ("1a", "Abu Dhabi"),
    ("1b", "Dubai"),
    ("1c", "Sharjah"),
    ("1d", "Ajman"),
    ("1e", "Umm Al Quwain"),
    ("1f", "Ras Al Khaimah"),
    ("1g", "Fujairah"),
]


class TaxCodeRateHistory(BaseModel):
    """Effective-dated rate for a TaxCode.

    The TaxCode carries the *current* rate for convenience; this table is the
    audit-grade source of what rate applied on any given date.
    """

    tax_code = models.ForeignKey(
        "accounts.TaxCode", on_delete=models.PROTECT, related_name="rate_history"
    )
    rate = models.DecimalField(max_digits=6, decimal_places=3)
    effective_from = models.DateField(db_index=True)
    effective_to = models.DateField(null=True, blank=True)
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["tax_code", "-effective_from"]
        constraints = [
            models.UniqueConstraint(
                fields=["tax_code", "effective_from"],
                name="tax_rate_history_unique_from",
            ),
        ]

    def __str__(self):
        return f"{self.tax_code_id} {self.rate}% from {self.effective_from}"


class TaxReturnStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    COMPUTED = "computed", "Computed"
    FILED = "filed", "Filed"
    PAID = "paid", "Paid"


class TaxReturn(BaseModel):
    """A FTA VAT 201 return for one filing period.

    Scoped to either a VAT group (multi-entity, shared TRN) or a single
    standalone entity. ``compute_vat_return`` populates the totals and boxes
    from the GL VAT control accounts across all member entities.
    """

    vat_group = models.ForeignKey(
        "tenants.VatGroup",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="vat_returns",
    )
    entity = models.ForeignKey(
        "tenants.Entity",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="vat_returns",
        help_text="Set for a standalone (non-grouped) filer; leave blank when vat_group is set.",
    )
    trn = models.CharField(max_length=15, blank=True)  # snapshot at compute time
    period_start = models.DateField()
    period_end = models.DateField(db_index=True)
    status = models.CharField(
        max_length=12, choices=TaxReturnStatus.choices, default=TaxReturnStatus.DRAFT, db_index=True
    )

    # Authoritative figures, derived from the GL VAT control accounts.
    total_output_vat = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    total_input_vat = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    net_vat_payable = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    computed_at = models.DateTimeField(null=True, blank=True)
    filed_at = models.DateTimeField(null=True, blank=True)
    filed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    filing_reference = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ["-period_end", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["vat_group", "period_start", "period_end"],
                condition=models.Q(vat_group__isnull=False),
                name="tax_return_unique_group_period",
            ),
            models.UniqueConstraint(
                fields=["entity", "period_start", "period_end"],
                condition=models.Q(entity__isnull=False),
                name="tax_return_unique_entity_period",
            ),
            models.CheckConstraint(
                check=models.Q(vat_group__isnull=False) | models.Q(entity__isnull=False),
                name="tax_return_scope_required",
            ),
        ]

    def __str__(self):
        scope = self.vat_group_id or self.entity_id or "?"
        return f"VAT201 {scope} {self.period_start}..{self.period_end} [{self.status}]"

    @property
    def member_entity_ids(self):
        """The entity ids this return aggregates across."""
        if self.vat_group_id:
            return list(self.vat_group.entities.values_list("id", flat=True))
        return [self.entity_id]


class TaxReturnBox(BaseModel):
    """One line of the VAT 201 form (a numbered box).

    Standard-rated supplies are split by emirate (Box 1a–1g). Summary boxes
    (output total, input total, net) carry the GL-derived figures.
    """

    tax_return = models.ForeignKey(TaxReturn, on_delete=models.CASCADE, related_name="boxes")
    box_code = models.CharField(max_length=8)  # "1a".."1g", "3", "4", "5", "12", "13", "14"
    label = models.CharField(max_length=128)
    emirate = models.CharField(max_length=32, blank=True)
    amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)  # net / taxable
    vat_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    adjustment = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["tax_return", "sort_order", "box_code"]
        constraints = [
            models.UniqueConstraint(
                fields=["tax_return", "box_code"], name="tax_return_box_unique"
            ),
        ]

    def __str__(self):
        return f"Box {self.box_code} {self.label}: {self.amount}/{self.vat_amount}"


class CorporateTaxReturn(BaseModel):
    """UAE Corporate Tax return — per entity per fiscal year (separate TRN).

    Tax is computed off accounting net profit with adjustments to taxable
    income. The 0% threshold and the standard rate are stored on the row
    (config-driven) so the engine never hardcodes statutory values.
    """

    entity = models.ForeignKey(
        "tenants.Entity", on_delete=models.PROTECT, related_name="corporate_tax_returns"
    )
    fiscal_year = models.PositiveSmallIntegerField()
    trn = models.CharField(max_length=20, blank=True)  # corporate tax TRN snapshot
    period_start = models.DateField()
    period_end = models.DateField()

    accounting_net_profit = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    adjustments = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    taxable_income = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    # Statutory parameters (config-driven; defaults reflect current UAE CT law).
    zero_band_threshold = models.DecimalField(
        max_digits=18, decimal_places=2, default=375000
    )  # 0% up to this taxable income
    tax_rate = models.DecimalField(max_digits=6, decimal_places=3, default=9)  # % above threshold
    small_business_relief = models.BooleanField(default=False)

    tax_payable = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    status = models.CharField(
        max_length=12, choices=TaxReturnStatus.choices, default=TaxReturnStatus.DRAFT, db_index=True
    )
    computed_at = models.DateTimeField(null=True, blank=True)
    filed_at = models.DateTimeField(null=True, blank=True)
    filed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    filing_reference = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ["entity", "-fiscal_year"]
        constraints = [
            models.UniqueConstraint(
                fields=["entity", "fiscal_year"], name="corporate_tax_unique_entity_year"
            ),
        ]

    def __str__(self):
        return f"CT {self.entity_id} FY{self.fiscal_year} [{self.status}]"
