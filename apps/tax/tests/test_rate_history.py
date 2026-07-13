"""Effective-dated VAT rate lookup."""

from datetime import date
from decimal import Decimal

import pytest

from apps.accounts.models import TaxCode
from apps.tax.models import TaxCodeRateHistory
from apps.tax.services.vat import rate_on

pytestmark = pytest.mark.django_db


@pytest.fixture
def tax_code(vat_group):
    return TaxCode.objects.create(
        entity=vat_group.entity_a,
        code="SR",
        name="Standard Rated",
        rate=Decimal("5.000"),
        treatment=TaxCode.Treatment.STANDARD,
    )


def test_rate_on_uses_effective_history(tax_code):
    TaxCodeRateHistory.objects.create(
        tax_code=tax_code,
        rate=Decimal("5.000"),
        effective_from=date(2018, 1, 1),
        effective_to=date(2026, 12, 31),
    )
    TaxCodeRateHistory.objects.create(
        tax_code=tax_code, rate=Decimal("7.500"), effective_from=date(2027, 1, 1)
    )
    assert rate_on(tax_code, date(2025, 6, 1)) == Decimal("5.000")
    assert rate_on(tax_code, date(2027, 6, 1)) == Decimal("7.500")


def test_rate_on_falls_back_to_live_rate(tax_code):
    # No history rows -> live rate on the tax code.
    assert rate_on(tax_code, date(2026, 6, 1)) == Decimal("5.000")
