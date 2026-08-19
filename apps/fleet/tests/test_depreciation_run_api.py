"""API tests for depreciation runs — draft create, then post builds lines."""

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from rest_framework.test import APIClient

import pytest

from apps.fleet.models import DepreciationRun, FleetDocStatus
from apps.tenants.models import UserEntityMembership

pytestmark = pytest.mark.django_db
User = get_user_model()

RUN_DATE = "2026-06-15"


def _client(entity, role=None):
    user = User.objects.create_user(email=f"{role or 'member'}@example.com", password="pw")
    UserEntityMembership.objects.create(user=user, entity=entity)
    if role:
        user.groups.add(Group.objects.get_or_create(name=role)[0])
    client = APIClient()
    client.force_authenticate(user)
    return client


def test_create_draft_then_post(entity, vehicle):
    client = _client(entity, "accountant")
    res = client.post(
        "/api/v1/depreciation-runs/",
        {"entity": str(entity.id), "run_date": RUN_DATE, "period_label": "Jun-2026"},
        format="json",
    )
    assert res.status_code == 201, res.content
    run_id = res.data["id"]
    assert res.data["status"] == FleetDocStatus.DRAFT
    assert res.data["lines"] == []

    res = client.post(f"/api/v1/depreciation-runs/{run_id}/post/")
    assert res.status_code == 200, res.content
    assert res.data["status"] == FleetDocStatus.POSTED
    assert res.data["run_no"].startswith("DEP-")
    assert res.data["total_amount"] == "2000.00"
    assert len(res.data["lines"]) == 1
    assert res.data["lines"][0]["vehicle_code"] == vehicle.code


def test_post_with_no_depreciable_vehicles_rejected(entity, vehicle):
    vehicle.useful_life_months = None
    vehicle.save(update_fields=["useful_life_months"])
    run = DepreciationRun.objects.create(entity=entity, run_date=date(2026, 6, 15))
    client = _client(entity, "accountant")
    res = client.post(f"/api/v1/depreciation-runs/{run.id}/post/")
    assert res.status_code == 400


def test_member_without_role_can_read_but_not_write(entity, vehicle):
    DepreciationRun.objects.create(entity=entity, run_date=date(2026, 6, 15))
    client = _client(entity, role=None)
    read = client.get("/api/v1/depreciation-runs/")
    assert read.status_code == 200
    assert len(read.data["results"]) == 1

    res = client.post(
        "/api/v1/depreciation-runs/",
        {"entity": str(entity.id), "run_date": RUN_DATE},
        format="json",
    )
    assert res.status_code == 403


def test_status_is_read_only_on_create(entity, vehicle):
    client = _client(entity, "accountant")
    res = client.post(
        "/api/v1/depreciation-runs/",
        {
            "entity": str(entity.id),
            "run_date": RUN_DATE,
            "status": FleetDocStatus.POSTED,
            "total_amount": Decimal("999999"),
        },
        format="json",
    )
    assert res.status_code == 201, res.content
    assert res.data["status"] == FleetDocStatus.DRAFT
    assert res.data["total_amount"] == "0.00"
