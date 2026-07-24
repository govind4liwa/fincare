"""API tests for driver master CRUD."""

from django.contrib.auth import get_user_model

from rest_framework.test import APIClient

import pytest

from apps.drivers.models import Driver

pytestmark = pytest.mark.django_db
User = get_user_model()


def _payload(entity):
    return {
        "entity": str(entity.id),
        "code": "D-100",
        "name": "Ramesh Kumar",
        "nationality": "Indian",
        "licence_no": "DXB-99887",
        "basic_salary": "2500.00",
        "commission_rate": "10.000",
    }


def _superuser():
    client = APIClient()
    client.force_authenticate(
        User.objects.create_superuser(email="root@example.com", password="pw")
    )
    return client


def test_create_and_update(entity):
    client = _superuser()
    res = client.post("/api/v1/drivers/", _payload(entity), format="json")
    assert res.status_code == 201, res.content
    did = res.data["id"]

    res = client.patch(f"/api/v1/drivers/{did}/", {"phone": "052-3334444"}, format="json")
    assert res.status_code == 200
    assert Driver.objects.get(id=did).phone == "052-3334444"
