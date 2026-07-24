"""UAE Corporate Tax computation tests (0% threshold, 9% above, SBR)."""

from datetime import date
from decimal import Decimal

import pytest

from apps.tax.models import CorporateTaxReturn, TaxReturnStatus
from apps.tax.services.corporate_tax import compute_corporate_tax

pytestmark = pytest.mark.django_db


def _ct(entity, profit, **kw):
    return CorporateTaxReturn.objects.create(
        entity=entity,
        fiscal_year=2026,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
        accounting_net_profit=Decimal(profit),
        **kw,
    )


def test_below_threshold_no_tax(vat_group):
    ret = compute_corporate_tax(_ct(vat_group.entity_a, "300000"))
    assert ret.taxable_income == Decimal("300000.00")
    assert ret.tax_payable == Decimal("0.00")
    assert ret.status == TaxReturnStatus.COMPUTED


def test_above_threshold_nine_percent_on_excess(vat_group):
    # 500,000 taxable -> 9% on (500,000 - 375,000) = 11,250
    ret = compute_corporate_tax(_ct(vat_group.entity_a, "500000"))
    assert ret.taxable_income == Decimal("500000.00")
    assert ret.tax_payable == Decimal("11250.00")


def test_adjustments_increase_taxable_income(vat_group):
    ret = compute_corporate_tax(_ct(vat_group.entity_a, "370000", adjustments=Decimal("10000")))
    assert ret.taxable_income == Decimal("380000.00")
    assert ret.tax_payable == Decimal("450.00")  # 9% of 5,000


def test_small_business_relief_zeroes_tax(vat_group):
    ret = compute_corporate_tax(_ct(vat_group.entity_a, "500000", small_business_relief=True))
    assert ret.tax_payable == Decimal("0.00")


def test_loss_makes_taxable_income_zero(vat_group):
    ret = compute_corporate_tax(_ct(vat_group.entity_a, "-50000"))
    assert ret.taxable_income == Decimal("0.00")
    assert ret.tax_payable == Decimal("0.00")


def test_filed_cannot_recompute(vat_group):
    ret = _ct(vat_group.entity_a, "500000")
    compute_corporate_tax(ret)
    ret.status = TaxReturnStatus.FILED
    ret.save(update_fields=["status"])
    from apps.tax.services.corporate_tax import CorporateTaxError

    with pytest.raises(CorporateTaxError):
        compute_corporate_tax(ret)
