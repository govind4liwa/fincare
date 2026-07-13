"""UAE Corporate Tax computation — per entity per fiscal year.

Tax is computed off accounting net profit adjusted to taxable income. Statutory
parameters (0% threshold and the standard rate) are read from the return row so
the engine never hardcodes the law; defaults reflect current UAE CT (0% up to
AED 375,000 taxable income, 9% above). Small Business Relief, when elected,
zeroes the liability.
"""

from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.utils import timezone

from apps.audit.services import record as audit_record
from apps.tax.models import CorporateTaxReturn, TaxReturnStatus

TWO_PLACES = Decimal("0.01")
ZERO = Decimal("0.00")


class CorporateTaxError(ValueError):
    """Raised when a corporate tax return cannot be computed."""


def _q(amount):
    return Decimal(amount).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


@transaction.atomic
def compute_corporate_tax(ct_return: CorporateTaxReturn, *, user=None) -> CorporateTaxReturn:
    """Compute taxable income and tax payable. Idempotent."""
    if ct_return.status == TaxReturnStatus.FILED:
        raise CorporateTaxError("Cannot recompute a filed corporate tax return.")

    taxable = _q(ct_return.accounting_net_profit + ct_return.adjustments)
    if taxable < ZERO:
        taxable = ZERO  # losses carry forward separately; no negative tax base here

    if ct_return.small_business_relief:
        tax = ZERO
    else:
        threshold = Decimal(ct_return.zero_band_threshold)
        rate = Decimal(ct_return.tax_rate) / Decimal(100)
        tax = _q((taxable - threshold) * rate) if taxable > threshold else ZERO

    ct_return.taxable_income = taxable
    ct_return.tax_payable = tax
    ct_return.trn = ct_return.entity.corporate_tax_trn or ct_return.trn
    ct_return.status = TaxReturnStatus.COMPUTED
    ct_return.computed_at = timezone.now()
    ct_return.save(
        update_fields=[
            "taxable_income",
            "tax_payable",
            "trn",
            "status",
            "computed_at",
            "updated_at",
        ]
    )

    audit_record(
        action="compute",
        instance=ct_return,
        actor=user,
        entity_id=ct_return.entity_id,
        message=f"Computed CT FY{ct_return.fiscal_year}: taxable={taxable} tax={tax}",
    )
    return ct_return
