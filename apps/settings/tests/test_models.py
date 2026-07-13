"""Tests for configuration models."""

from django.db import IntegrityError, transaction

import pytest

from apps.settings.models import EntitySetting, FeatureFlag
from apps.tenants.models import BusinessCategory, Entity

pytestmark = pytest.mark.django_db


@pytest.fixture
def entity():
    cat = BusinessCategory.objects.create(
        key="transport", label="Transport", band="1", coa_template_key="transport"
    )
    return Entity.objects.create(
        code="RGT", numeric_code="101", legal_name="Regency Transport LLC", category=cat
    )


def test_entity_setting_unique_per_key(entity):
    EntitySetting.objects.create(entity=entity, key="fiscal_year_start", value={"month": 1})
    with pytest.raises(IntegrityError), transaction.atomic():
        EntitySetting.objects.create(entity=entity, key="fiscal_year_start", value={"month": 4})


def test_json_value_roundtrip(entity):
    s = EntitySetting.objects.create(entity=entity, key="vat", value={"rate": "5.000"})
    s.refresh_from_db()
    assert s.value == {"rate": "5.000"}


def test_feature_flag_default_off(entity):
    flag = FeatureFlag.objects.create(entity=entity, flag="trip_invoicing")
    assert flag.enabled is False
