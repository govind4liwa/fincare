"""API tests for vehicle documents — renewal history + expiry alerts."""

from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from rest_framework.test import APIClient

import pytest

from apps.fleet.models import VehicleDocument
from apps.tenants.models import UserEntityMembership

pytestmark = pytest.mark.django_db
User = get_user_model()


def _client(entity, role=None):
    user = User.objects.create_user(email=f"{role or 'member'}@example.com", password="pw")
    UserEntityMembership.objects.create(user=user, entity=entity)
    if role:
        user.groups.add(Group.objects.get_or_create(name=role)[0])
    client = APIClient()
    client.force_authenticate(user)
    return client


def test_accountant_can_create_a_document(entity, vehicle):
    client = _client(entity, "accountant")
    res = client.post(
        "/api/v1/vehicle-documents/",
        {
            "vehicle": str(vehicle.id),
            "doc_type": "insurance",
            "doc_no": "POL-123",
            "expiry_date": "2026-07-01",
        },
        format="json",
    )
    assert res.status_code == 201, res.content
    assert res.data["vehicle_code"] == vehicle.code
    assert res.data["days_to_expiry"] is not None


def test_member_without_role_can_read_but_not_write(entity, vehicle):
    VehicleDocument.objects.create(
        vehicle=vehicle, doc_type=VehicleDocument.DocType.INSURANCE, expiry_date=date(2026, 7, 1)
    )
    client = _client(entity, role=None)
    read = client.get("/api/v1/vehicle-documents/")
    assert read.status_code == 200
    assert len(read.data["results"]) == 1

    res = client.post(
        "/api/v1/vehicle-documents/",
        {"vehicle": str(vehicle.id), "doc_type": "permit"},
        format="json",
    )
    assert res.status_code == 403


def test_expiring_endpoint_filters_within_window(entity, vehicle):
    VehicleDocument.objects.create(
        vehicle=vehicle, doc_type=VehicleDocument.DocType.INSURANCE, expiry_date=date(2026, 7, 1)
    )
    VehicleDocument.objects.create(
        vehicle=vehicle, doc_type=VehicleDocument.DocType.REGISTRATION, expiry_date=date(2027, 1, 1)
    )
    client = _client(entity, "accountant")
    res = client.get(f"/api/v1/vehicle-documents/expiring/?entity={entity.id}&within_days=30")
    assert res.status_code == 200
    assert [d["doc_type"] for d in res.data["documents"]] == ["insurance"]


def test_delete_disabled(entity, vehicle):
    doc = VehicleDocument.objects.create(
        vehicle=vehicle, doc_type=VehicleDocument.DocType.PERMIT, expiry_date=date(2026, 7, 1)
    )
    client = _client(entity, "admin")
    deleted = client.delete(f"/api/v1/vehicle-documents/{doc.id}/")
    assert deleted.status_code == 405
