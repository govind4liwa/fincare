"""API tests for drivers — membership scoping."""

from django.contrib.auth import get_user_model

from rest_framework.test import APIClient

import pytest

from apps.drivers.models import Driver
from apps.tenants.models import BusinessCategory, Entity, UserEntityMembership

pytestmark = pytest.mark.django_db
User = get_user_model()


@pytest.fixture
def driver():
    cat = BusinessCategory.objects.create(
        key="transport", label="Transport", band="1", coa_template_key="transport"
    )
    ent = Entity.objects.create(code="E1", numeric_code="101", legal_name="E1 LLC", category=cat)
    return Driver.objects.create(entity=ent, code="D001", name="Rahul Kumar", nationality="Indian")


def test_member_sees_drivers(driver):
    user = User.objects.create_user(email="drv@example.com", password="pw")
    UserEntityMembership.objects.create(user=user, entity=driver.entity)
    client = APIClient()
    client.force_authenticate(user)
    res = client.get("/api/v1/drivers/")
    assert res.status_code == 200
    assert {d["code"] for d in res.data["results"]} == {"D001"}


def test_non_member_sees_nothing(driver):
    user = User.objects.create_user(email="x@example.com", password="pw")
    client = APIClient()
    client.force_authenticate(user)
    assert client.get("/api/v1/drivers/").data["results"] == []


def test_unauthenticated_is_rejected():
    assert APIClient().get("/api/v1/drivers/").status_code == 401
