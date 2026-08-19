"""API tests for VAT 201 returns, Corporate Tax returns, and rate history."""

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from rest_framework.test import APIClient

import pytest

from apps.accounts.models import TaxCode
from apps.tax.models import CorporateTaxReturn, TaxReturnStatus
from apps.tenants.models import UserEntityMembership

pytestmark = pytest.mark.django_db
User = get_user_model()

START = date(2026, 6, 1)
END = date(2026, 6, 30)


def _client(entity, role=None):
    user = User.objects.create_user(email=f"{role or 'member'}@example.com", password="pw")
    UserEntityMembership.objects.create(user=user, entity=entity)
    if role:
        user.groups.add(Group.objects.get_or_create(name=role)[0])
    client = APIClient()
    client.force_authenticate(user)
    return client


def test_vat_return_compute_then_file(vat_group, post_sale, post_purchase):
    post_sale(vat_group.entity_a, amount="1000", place_of_supply="Dubai")
    post_purchase(vat_group.entity_b, amount="2000")
    client = _client(vat_group.entity_a, "accountant")

    res = client.post(
        "/api/v1/vat-returns/",
        {"vat_group": str(vat_group.id), "period_start": str(START), "period_end": str(END)},
        format="json",
    )
    assert res.status_code == 201, res.content
    return_id = res.data["id"]
    assert res.data["status"] == TaxReturnStatus.DRAFT

    res = client.post(f"/api/v1/vat-returns/{return_id}/compute/")
    assert res.status_code == 200, res.content
    assert res.data["status"] == TaxReturnStatus.COMPUTED
    assert res.data["total_output_vat"] == "50.00"
    assert res.data["total_input_vat"] == "100.00"
    assert len(res.data["boxes"]) == 10  # 7 emirates + 3 summary boxes

    res = client.post(f"/api/v1/vat-returns/{return_id}/file/", {"reference": "FTA-REF-1"})
    assert res.status_code == 200, res.content
    assert res.data["status"] == TaxReturnStatus.FILED
    assert res.data["filing_reference"] == "FTA-REF-1"

    # A filed return cannot be recomputed.
    res = client.post(f"/api/v1/vat-returns/{return_id}/compute/")
    assert res.status_code == 400


def test_member_of_group_entity_sees_group_return(vat_group, post_sale, post_purchase):
    post_sale(vat_group.entity_a, amount="1000", place_of_supply="Dubai")
    client = _client(vat_group.entity_a, "accountant")
    res = client.post(
        "/api/v1/vat-returns/",
        {"vat_group": str(vat_group.id), "period_start": str(START), "period_end": str(END)},
        format="json",
    )
    return_id = res.data["id"]

    # A user who is only a member of the *other* group entity should still see it.
    other_member = _client(vat_group.entity_b, role=None)
    read = other_member.get("/api/v1/vat-returns/")
    assert read.status_code == 200
    assert {r["id"] for r in read.data["results"]} == {return_id}


def test_non_member_sees_nothing(vat_group):
    outsider = User.objects.create_user(email="outsider@example.com", password="pw")
    client = APIClient()
    client.force_authenticate(outsider)
    res = client.get("/api/v1/vat-returns/")
    assert res.status_code == 200
    assert res.data["results"] == []


def test_vat_return_write_requires_role(vat_group):
    client = _client(vat_group.entity_a, role=None)
    res = client.post(
        "/api/v1/vat-returns/",
        {"vat_group": str(vat_group.id), "period_start": str(START), "period_end": str(END)},
        format="json",
    )
    assert res.status_code == 403


def test_corporate_tax_compute_then_file(vat_group):
    client = _client(vat_group.entity_a, "accountant")
    res = client.post(
        "/api/v1/corporate-tax-returns/",
        {
            "entity": str(vat_group.entity_a.id),
            "fiscal_year": 2026,
            "period_start": "2026-01-01",
            "period_end": "2026-12-31",
            "accounting_net_profit": "500000",
        },
        format="json",
    )
    assert res.status_code == 201, res.content
    return_id = res.data["id"]

    res = client.post(f"/api/v1/corporate-tax-returns/{return_id}/compute/")
    assert res.status_code == 200, res.content
    assert res.data["tax_payable"] == "11250.00"  # 9% of (500,000 - 375,000)
    assert res.data["status"] == TaxReturnStatus.COMPUTED

    res = client.post(f"/api/v1/corporate-tax-returns/{return_id}/file/", {"reference": "CT-REF-1"})
    assert res.status_code == 200, res.content
    assert res.data["status"] == TaxReturnStatus.FILED

    ct = CorporateTaxReturn.objects.get(id=return_id)
    assert ct.filed_by is not None


def test_corporate_tax_cannot_file_before_compute(vat_group):
    client = _client(vat_group.entity_a, "accountant")
    res = client.post(
        "/api/v1/corporate-tax-returns/",
        {
            "entity": str(vat_group.entity_a.id),
            "fiscal_year": 2026,
            "period_start": "2026-01-01",
            "period_end": "2026-12-31",
            "accounting_net_profit": "500000",
        },
        format="json",
    )
    return_id = res.data["id"]
    res = client.post(f"/api/v1/corporate-tax-returns/{return_id}/file/")
    assert res.status_code == 400


def test_rate_history_crud(vat_group):
    tax_code = TaxCode.objects.create(
        entity=vat_group.entity_a,
        code="SR",
        name="Standard Rated 5%",
        rate=Decimal("5.000"),
        treatment=TaxCode.Treatment.STANDARD,
    )
    client = _client(vat_group.entity_a, "accountant")
    res = client.post(
        "/api/v1/tax-rate-history/",
        {"tax_code": str(tax_code.id), "rate": "5.000", "effective_from": "2026-01-01"},
        format="json",
    )
    assert res.status_code == 201, res.content
    assert res.data["tax_code_code"] == "SR"

    read = _client(vat_group.entity_a, role=None).get("/api/v1/tax-rate-history/")
    assert read.status_code == 200
    assert len(read.data["results"]) == 1
