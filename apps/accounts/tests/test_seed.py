"""Tests for category-template COA seeding."""

import re

import pytest

from apps.accounts.models import Account, AccountGroup
from apps.accounts.services.seed import seed_entity_coa, seed_tax_codes
from apps.accounts.services.templates import account_rows
from apps.tenants.models import BusinessCategory, Entity

pytestmark = pytest.mark.django_db

CODE_RE = re.compile(r"^\d{3}-\d{3}-\d{3}-\d{3}$")


@pytest.fixture
def transport_entity():
    cat = BusinessCategory.objects.create(
        key="transport", label="Transport", band="1", coa_template_key="transport"
    )
    return Entity.objects.create(
        code="RGT", numeric_code="101", legal_name="Regency Transport LLC", category=cat
    )


def test_seed_creates_expected_account_count(transport_entity):
    result = seed_entity_coa(transport_entity)
    expected = len(account_rows("transport"))  # 85
    assert result["accounts_created"] == expected
    assert Account.objects.filter(entity=transport_entity).count() == expected
    assert AccountGroup.objects.filter(entity=transport_entity, level=1).exists()
    assert AccountGroup.objects.filter(entity=transport_entity, level=2).exists()


def test_seed_is_idempotent(transport_entity):
    seed_entity_coa(transport_entity)
    second = seed_entity_coa(transport_entity)
    assert second["accounts_created"] == 0
    assert second["groups_created"] == 0


def test_all_codes_match_pattern_and_band(transport_entity):
    seed_entity_coa(transport_entity)
    codes = list(Account.objects.filter(entity=transport_entity).values_list("code", flat=True))
    assert codes, "expected accounts"
    assert all(CODE_RE.match(c) for c in codes)
    assert all(c.startswith("101-") for c in codes)


def test_known_accounts_present_and_typed(transport_entity):
    seed_entity_coa(transport_entity)
    uber = Account.objects.get(code="101-400-410-001")
    assert uber.name == "Uber Earnings"
    assert uber.account_type == "revenue"
    assert uber.normal_balance == "C"


def test_control_account_blocks_manual_posting(transport_entity):
    seed_entity_coa(transport_entity)
    ar = Account.objects.get(entity=transport_entity, is_control_account=True, subledger="customer")
    assert ar.allow_manual_posting is False


def test_band_mismatch_raises():
    cat = BusinessCategory.objects.create(
        key="transport", label="Transport", band="1", coa_template_key="transport"
    )
    wrong = Entity.objects.create(
        code="X", numeric_code="201", legal_name="Wrong band", category=cat
    )
    with pytest.raises(ValueError):
        seed_entity_coa(wrong)


def test_seed_tax_codes_idempotent(transport_entity):
    assert seed_tax_codes(transport_entity) == 6
    assert seed_tax_codes(transport_entity) == 0
