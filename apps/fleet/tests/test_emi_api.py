"""API tests for vehicle loans and EMI schedules: flow, isolation, permissions."""

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from rest_framework.test import APIClient

import pytest

from apps.fleet.models import AmortizationMethod, FleetDocStatus, LoanSchedule, VehicleLoan
from apps.tenants.models import UserEntityMembership

pytestmark = pytest.mark.django_db
User = get_user_model()

D = Decimal
VEHICLE_LOAN = "101-200-220-001"
LOAN_INTEREST = "101-700-710-001"


def _superuser():
    client = APIClient()
    client.force_authenticate(
        User.objects.create_superuser(email="root@example.com", password="pw")
    )
    return client


@pytest.fixture
def flat_loan(entity, vehicle, acct):
    return VehicleLoan.objects.create(
        entity=entity,
        vehicle=vehicle,
        lender="ENBD Auto Finance",
        loan_account=acct(VEHICLE_LOAN),
        interest_account=acct(LOAN_INTEREST),
        principal=D("12000"),
        term_months=12,
        annual_interest_rate=D("0"),
        amortization_method=AmortizationMethod.FLAT_RATE,
        first_payment_date=date(2026, 6, 15),
    )


def test_create_loan_records_both_rates(entity, vehicle, acct):
    payload = {
        "entity": str(entity.id),
        "vehicle": str(vehicle.id),
        "lender": "ADCB Auto",
        "loan_account": str(acct(VEHICLE_LOAN).id),
        "interest_account": str(acct(LOAN_INTEREST).id),
        "principal": "100000.00",
        "term_months": 48,
        "annual_interest_rate": "6.500",
        "amortization_method": AmortizationMethod.FLAT_RATE,
        "quoted_flat_rate": "2.500",
        "effective_annual_rate": "4.750",
        "first_payment_date": "2026-06-15",
    }
    res = _superuser().post("/api/v1/vehicle-loans/", payload, format="json")
    assert res.status_code == 201, res.content
    assert res.data["quoted_flat_rate"] == "2.500"
    assert res.data["effective_annual_rate"] == "4.750"
    assert res.data["approved_schedule_version"] is None


def test_generate_approve_and_post_flow(flat_loan, bank_enbd):
    client = _superuser()

    gen = client.post(f"/api/v1/vehicle-loans/{flat_loan.id}/generate-schedule/", {}, format="json")
    assert gen.status_code == 201, gen.content
    assert gen.data["status"] == LoanSchedule.Status.DRAFT
    assert gen.data["version_no"] == 1
    assert len(gen.data["installments"]) == 12
    assert gen.data["total_principal"] == "12000.00"
    schedule_id = gen.data["id"]
    first = gen.data["installments"][0]

    # Cannot post from a draft schedule.
    early = client.post(
        f"/api/v1/loan-installments/{first['id']}/post/",
        {"bank_account": str(bank_enbd.id)},
        format="json",
    )
    assert early.status_code == 400

    approved = client.post(f"/api/v1/loan-schedules/{schedule_id}/approve/", {}, format="json")
    assert approved.status_code == 200
    assert approved.data["status"] == LoanSchedule.Status.APPROVED

    posted = client.post(
        f"/api/v1/loan-installments/{first['id']}/post/",
        {"bank_account": str(bank_enbd.id)},
        format="json",
    )
    assert posted.status_code == 200, posted.content
    assert posted.data["status"] == FleetDocStatus.POSTED
    assert posted.data["journal_entry"] is not None

    # The loan now reports its approved version.
    loan = client.get(f"/api/v1/vehicle-loans/{flat_loan.id}/").data
    assert loan["approved_schedule_version"] == 1


def test_regeneration_is_a_new_version(flat_loan):
    client = _superuser()
    first = client.post(
        f"/api/v1/vehicle-loans/{flat_loan.id}/generate-schedule/", {}, format="json"
    )
    client.post(f"/api/v1/loan-schedules/{first.data['id']}/approve/", {}, format="json")
    second = client.post(
        f"/api/v1/vehicle-loans/{flat_loan.id}/generate-schedule/",
        {"note": "rescheduled"},
        format="json",
    )
    assert second.data["version_no"] == 2

    listing = client.get(f"/api/v1/vehicle-loans/{flat_loan.id}/schedules/").data["schedules"]
    assert [s["version_no"] for s in listing] == [2, 1]


def test_discard_draft_but_not_approved(flat_loan):
    client = _superuser()
    draft = client.post(
        f"/api/v1/vehicle-loans/{flat_loan.id}/generate-schedule/", {}, format="json"
    ).data
    discarded = client.post(f"/api/v1/loan-schedules/{draft['id']}/discard/", {}, format="json")
    assert discarded.status_code == 204

    approved = client.post(
        f"/api/v1/vehicle-loans/{flat_loan.id}/generate-schedule/", {}, format="json"
    ).data
    client.post(f"/api/v1/loan-schedules/{approved['id']}/approve/", {}, format="json")
    refused = client.post(f"/api/v1/loan-schedules/{approved['id']}/discard/", {}, format="json")
    assert refused.status_code == 400


def test_generation_error_is_reported(entity, vehicle, acct):
    loan = VehicleLoan.objects.create(
        entity=entity,
        vehicle=vehicle,
        loan_account=acct(VEHICLE_LOAN),
        interest_account=acct(LOAN_INTEREST),
        principal=D("10000"),
        term_months=0,  # no term → cannot generate
        first_payment_date=date(2026, 6, 15),
    )
    res = _superuser().post(
        f"/api/v1/vehicle-loans/{loan.id}/generate-schedule/", {}, format="json"
    )
    assert res.status_code == 400
    assert "detail" in res.data


# --- isolation & permissions ------------------------------------------------


def test_loans_and_schedules_are_entity_scoped(flat_loan):
    _superuser().post(f"/api/v1/vehicle-loans/{flat_loan.id}/generate-schedule/", {}, format="json")

    outsider = User.objects.create_user(email="out@example.com", password="pw")
    outsider.groups.add(Group.objects.create(name="accountant"))
    client = APIClient()
    client.force_authenticate(outsider)

    assert client.get("/api/v1/vehicle-loans/").data["results"] == []
    assert client.get("/api/v1/loan-schedules/").data["results"] == []
    assert client.get("/api/v1/loan-installments/").data["results"] == []


def test_member_without_role_can_read_but_not_write(entity, flat_loan):
    user = User.objects.create_user(email="viewer@example.com", password="pw")
    UserEntityMembership.objects.create(user=user, entity=entity)
    client = APIClient()
    client.force_authenticate(user)

    read = client.get("/api/v1/vehicle-loans/")
    assert read.status_code == 200
    assert len(read.data["results"]) == 1

    denied = client.post(
        f"/api/v1/vehicle-loans/{flat_loan.id}/generate-schedule/", {}, format="json"
    )
    assert denied.status_code == 403


def test_unauthenticated_rejected():
    res = APIClient().get("/api/v1/vehicle-loans/")
    assert res.status_code == 401
