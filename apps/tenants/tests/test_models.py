"""Tests for tenancy models."""

import uuid

from django.db import IntegrityError, transaction

import pytest

from apps.tenants.models import Branch, BusinessCategory, Entity, VatGroup

pytestmark = pytest.mark.django_db


@pytest.fixture
def category():
    return BusinessCategory.objects.create(
        key="transport", label="Transport", band="1", coa_template_key="transport"
    )


def _entity(category, code="RGT", numeric_code="101", **extra):
    return Entity.objects.create(
        code=code,
        numeric_code=numeric_code,
        legal_name=f"{code} LLC",
        category=category,
        **extra,
    )


def test_category_band_is_unique(category):
    with pytest.raises(IntegrityError), transaction.atomic():
        BusinessCategory.objects.create(
            key="cafeteria", label="Cafeteria", band="1", coa_template_key="cafeteria"
        )


def test_entity_numeric_code_unique(category):
    _entity(category, code="RGT", numeric_code="101")
    with pytest.raises(IntegrityError), transaction.atomic():
        _entity(category, code="OTHER", numeric_code="101")


def test_entity_pk_is_uuid(category):
    e = _entity(category)
    assert isinstance(e.pk, uuid.UUID)


def test_effective_trn_resolves_from_vat_group(category):
    vg = VatGroup.objects.create(code="VG-01", name="Regency VAT Group", trn="100123456700003")
    e = _entity(category, vat_group=vg)
    assert e.effective_trn == "100123456700003"


def test_effective_trn_none_without_group(category):
    e = _entity(category)
    assert e.effective_trn is None


def test_branch_code_unique_within_entity(category):
    e = _entity(category)
    Branch.objects.create(entity=e, code="DXB", name="Dubai")
    with pytest.raises(IntegrityError), transaction.atomic():
        Branch.objects.create(entity=e, code="DXB", name="Dubai 2")


def test_branch_code_reusable_across_entities(category):
    e1 = _entity(category, code="E1", numeric_code="101")
    e2 = _entity(category, code="E2", numeric_code="102")
    Branch.objects.create(entity=e1, code="DXB", name="Dubai")
    # same branch code under a different entity is allowed
    Branch.objects.create(entity=e2, code="DXB", name="Dubai")
    assert Branch.objects.filter(code="DXB").count() == 2
