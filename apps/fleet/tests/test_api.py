"""API tests for fleet vehicles — membership scoping."""

from django.contrib.auth import get_user_model

from rest_framework.test import APIClient

import pytest

from apps.fleet.models import Vehicle
from apps.tenants.models import BusinessCategory, Entity, UserEntityMembership

pytestmark = pytest.mark.django_db
User = get_user_model()


@pytest.fixture
def vehicle():
    cat = BusinessCategory.objects.create(
        key="transport", label="Transport", band="1", coa_template_key="transport"
    )
    ent = Entity.objects.create(code="E1", numeric_code="101", legal_name="E1 LLC", category=cat)
    return Vehicle.objects.create(
        entity=ent, code="V001", plate_no="A12345", make="Toyota", model="Camry"
    )


def test_member_sees_vehicles(vehicle):
    user = User.objects.create_user(email="fleet@example.com", password="pw")
    UserEntityMembership.objects.create(user=user, entity=vehicle.entity)
    client = APIClient()
    client.force_authenticate(user)
    res = client.get("/api/v1/vehicles/")
    assert res.status_code == 200
    assert {v["code"] for v in res.data["results"]} == {"V001"}


def test_non_member_sees_nothing(vehicle):
    user = User.objects.create_user(email="x@example.com", password="pw")
    client = APIClient()
    client.force_authenticate(user)
    assert client.get("/api/v1/vehicles/").data["results"] == []


def test_unauthenticated_is_rejected():
    assert APIClient().get("/api/v1/vehicles/").status_code == 401
