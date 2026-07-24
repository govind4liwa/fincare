"""API tests for vehicle master CRUD."""

from django.contrib.auth import get_user_model

from rest_framework.test import APIClient

import pytest

from apps.fleet.models import Vehicle

pytestmark = pytest.mark.django_db
User = get_user_model()


def _payload(entity):
    return {
        "entity": str(entity.id),
        "code": "V-100",
        "plate_no": "A 12345",
        "plate_emirate": "Dubai",
        "make": "Toyota",
        "model": "Hiace",
        "model_year": 2024,
        "ownership": "owned",
    }


def _superuser():
    client = APIClient()
    client.force_authenticate(
        User.objects.create_superuser(email="root@example.com", password="pw")
    )
    return client


def test_create_and_update(entity):
    client = _superuser()
    res = client.post("/api/v1/vehicles/", _payload(entity), format="json")
    assert res.status_code == 201, res.content
    vid = res.data["id"]

    res = client.patch(f"/api/v1/vehicles/{vid}/", {"is_active": False}, format="json")
    assert res.status_code == 200
    assert Vehicle.objects.get(id=vid).is_active is False
