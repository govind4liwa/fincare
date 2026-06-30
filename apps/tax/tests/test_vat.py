"""VAT 201 computation tests: GL-driven totals, multi-entity aggregation, emirate split."""

from datetime import date
from decimal import Decimal

import pytest
from django.db.utils import IntegrityError

from apps.tax.models import TaxReturn, TaxReturnStatus
from apps.tax.services.vat import TaxError, compute_vat_return, file_vat_return

pytestmark = pytest.mark.django_db

START = date(2026, 6, 1)
END = date(2026, 6, 30)


def _group_return(vat_group):
    return TaxReturn.objects.create(vat_group=vat_group, period_start=START, period_end=END)


def test_group_return_sums_output_and_input_across_entities(vat_group, post_sale, post_purchase):
    # Output VAT 50 in entity A; Input VAT 100 in entity B.
    post_sale(vat_group.entity_a, amount="1000", place_of_supply="Dubai")
    post_purchase(vat_group.entity_b, amount="2000")

    ret = compute_vat_return(_group_return(vat_group))

    assert ret.status == TaxReturnStatus.COMPUTED
    assert ret.trn == "100123456700003"  # snapshot from the VAT group
    assert ret.total_output_vat == Decimal("50.00")
    assert ret.total_input_vat == Decimal("100.00")
    assert ret.net_vat_payable == Decimal("-50.00")  # net reclaimable


def test_summary_boxes_match_gl(vat_group, post_sale, post_purchase):
    post_sale(vat_group.entity_a, amount="1000", place_of_supply="Dubai")
    post_purchase(vat_group.entity_b, amount="2000")

    ret = compute_vat_return(_group_return(vat_group))
    boxes = {b.box_code: b for b in ret.boxes.all()}

    assert boxes["12"].vat_amount == Decimal("50.00")  # output tax due
    assert boxes["13"].vat_amount == Decimal("100.00")  # input tax recoverable
    assert boxes["14"].vat_amount == Decimal("-50.00")  # net


def test_emirate_split_box_for_standard_rated_sales(vat_group, post_sale):
    post_sale(vat_group.entity_a, amount="1000", place_of_supply="Dubai")

    ret = compute_vat_return(_group_return(vat_group))
    boxes = {b.box_code: b for b in ret.boxes.all()}

    # Box 1b = Dubai
    assert boxes["1b"].emirate == "Dubai"
    assert boxes["1b"].amount == Decimal("1000.00")
    assert boxes["1b"].vat_amount == Decimal("50.00")
    # Abu Dhabi (1a) had no supplies
    assert boxes["1a"].amount == Decimal("0.00")
    # All seven emirate boxes always present
    assert {"1a", "1b", "1c", "1d", "1e", "1f", "1g"} <= set(boxes)


def test_recompute_is_idempotent(vat_group, post_sale):
    post_sale(vat_group.entity_a, amount="1000", place_of_supply="Dubai")
    ret = _group_return(vat_group)

    compute_vat_return(ret)
    first_count = ret.boxes.count()
    compute_vat_return(ret)

    ret.refresh_from_db()
    assert ret.boxes.count() == first_count  # boxes rebuilt, not duplicated
    assert ret.total_output_vat == Decimal("50.00")


def test_filed_return_cannot_recompute(vat_group, post_sale):
    post_sale(vat_group.entity_a, amount="1000", place_of_supply="Dubai")
    ret = compute_vat_return(_group_return(vat_group))
    file_vat_return(ret, reference="FTA-REF-1")

    ret.refresh_from_db()
    assert ret.status == TaxReturnStatus.FILED
    with pytest.raises(TaxError):
        compute_vat_return(ret)


def test_out_of_period_movements_excluded(vat_group, post_sale):
    post_sale(vat_group.entity_a, amount="1000", place_of_supply="Dubai")

    # A return for a prior, empty period sees nothing.
    prior = TaxReturn.objects.create(
        vat_group=vat_group, period_start=date(2026, 5, 1), period_end=date(2026, 5, 31)
    )
    ret = compute_vat_return(prior)
    assert ret.total_output_vat == Decimal("0.00")
    assert ret.total_input_vat == Decimal("0.00")


def test_scope_requires_group_or_entity(db):
    with pytest.raises(IntegrityError):  # tax_return_scope_required CheckConstraint
        TaxReturn.objects.create(period_start=START, period_end=END)
