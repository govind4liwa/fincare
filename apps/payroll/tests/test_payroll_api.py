"""API tests for payroll: employee masters, salary structure, and the
run -> payslip lifecycle (build -> post -> pay)."""

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from rest_framework.test import APIClient

import pytest

from apps.payroll.models import Advance, ComponentType, Run, RunStatus, SalaryComponent
from apps.payroll.tests.conftest import STAFF_ADVANCES
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


def test_member_without_role_can_read_but_not_write_employee(entity, employee):
    client = _client(entity, role=None)
    read = client.get("/api/v1/employees/")
    assert read.status_code == 200
    assert {e["code"] for e in read.data["results"]} == {"E001"}
    assert len(read.data["results"][0]["salary"]) == 2

    res = client.post(
        "/api/v1/employees/",
        {"entity": str(entity.id), "code": "E999", "name": "X"},
        format="json",
    )
    assert res.status_code == 403


def test_group_wide_salary_component_visible_to_member(entity, components):
    SalaryComponent.objects.create(
        entity=None,
        code="GROUP_WIDE",
        name="Group-wide default",
        component_type=ComponentType.DEDUCTION,
    )
    client = _client(entity, role=None)
    res = client.get("/api/v1/salary-components/")
    assert res.status_code == 200
    codes = {c["code"] for c in res.data["results"]}
    assert "GROUP_WIDE" in codes
    assert "BASIC" in codes


def test_create_employee_salary(entity, employee, components):
    client = _client(entity, "accountant")
    res = client.post(
        "/api/v1/employee-salaries/",
        {
            "employee": str(employee.id),
            "component": str(components["BASIC"].id),
            "amount": "3500.00",
            "effective_from": "2026-07-01",
        },
        format="json",
    )
    assert res.status_code == 201, res.content
    assert res.data["component_code"] == "BASIC"


def test_run_build_then_post_then_pay(entity, employee, bank_enbd):
    client = _client(entity, "accountant")
    res = client.post(
        "/api/v1/payroll-runs/",
        {"entity": str(entity.id), "salary_month": "2026-06", "run_date": "2026-06-30"},
        format="json",
    )
    assert res.status_code == 201, res.content
    run_id = res.data["id"]
    assert res.data["status"] == RunStatus.DRAFT

    res = client.post(f"/api/v1/payroll-runs/{run_id}/build/")
    assert res.status_code == 200, res.content
    assert res.data["gross_total"] == "4000.00"
    assert res.data["net_total"] == "4000.00"
    assert len(res.data["payslips"]) == 1

    res = client.post(f"/api/v1/payroll-runs/{run_id}/post/")
    assert res.status_code == 200, res.content
    assert res.data["status"] == RunStatus.POSTED

    res = client.post(f"/api/v1/payroll-runs/{run_id}/pay/", {"bank_account": str(bank_enbd.id)})
    assert res.status_code == 200, res.content
    assert res.data["status"] == RunStatus.PAID

    run = Run.objects.get(id=run_id)
    assert run.payment_entry is not None
    assert run.payment_entry.total_debit == run.payment_entry.total_credit == Decimal("4000.00")


def test_pay_before_post_rejected(entity, employee, bank_enbd):
    client = _client(entity, "accountant")
    run = Run.objects.create(entity=entity, salary_month="2026-06", run_date=date(2026, 6, 30))
    res = client.post(f"/api/v1/payroll-runs/{run.id}/pay/", {"bank_account": str(bank_enbd.id)})
    assert res.status_code == 400


def test_pay_requires_bank_account(entity, employee):
    client = _client(entity, "accountant")
    run = Run.objects.create(entity=entity, salary_month="2026-06", run_date=date(2026, 6, 30))
    client.post(f"/api/v1/payroll-runs/{run.id}/build/")
    client.post(f"/api/v1/payroll-runs/{run.id}/post/")
    res = client.post(f"/api/v1/payroll-runs/{run.id}/pay/")
    assert res.status_code == 400


def test_payslips_are_read_only(entity, employee):
    client = _client(entity, "accountant")
    run = Run.objects.create(entity=entity, salary_month="2026-06", run_date=date(2026, 6, 30))
    client.post(f"/api/v1/payroll-runs/{run.id}/build/")
    res = client.get(f"/api/v1/payslips/?run={run.id}")
    assert res.status_code == 200
    assert len(res.data["results"]) == 1
    payslip_id = res.data["results"][0]["id"]
    res = client.post(f"/api/v1/payslips/{payslip_id}/", {}, format="json")
    assert res.status_code == 405


def test_run_write_requires_role(entity):
    client = _client(entity, role=None)
    res = client.post(
        "/api/v1/payroll-runs/",
        {"entity": str(entity.id), "salary_month": "2026-06", "run_date": "2026-06-30"},
        format="json",
    )
    assert res.status_code == 403


def test_create_advance_then_pay(entity, employee, acct, bank_enbd):
    client = _client(entity, "accountant")
    res = client.post(
        "/api/v1/payroll-advances/",
        {
            "entity": str(entity.id),
            "employee": str(employee.id),
            "advance_date": "2026-06-01",
            "amount": "1200.00",
            "installments": 3,
            "advance_account": str(acct(STAFF_ADVANCES).id),
            "bank_account": str(bank_enbd.id),
        },
        format="json",
    )
    assert res.status_code == 201, res.content
    advance_id = res.data["id"]
    assert res.data["status"] == Advance.Status.OPEN
    assert res.data["balance"] == "0.00"  # not meaningful until paid

    res = client.post(f"/api/v1/payroll-advances/{advance_id}/pay/")
    assert res.status_code == 200, res.content
    assert res.data["balance"] == "1200.00"
    assert res.data["installment_amount"] == "400.00"  # even split, auto-computed

    advance = Advance.objects.get(id=advance_id)
    je = advance.journal_entry
    assert je.total_debit == je.total_credit == Decimal("1200.00")
    lines = {ln.account.code: (ln.debit, ln.credit) for ln in je.lines.all()}
    assert lines[STAFF_ADVANCES] == (Decimal("1200.00"), Decimal("0.00"))
    assert lines[bank_enbd.gl_account.code] == (Decimal("0.00"), Decimal("1200.00"))


def test_pay_advance_requires_bank_account(entity, employee, acct):
    client = _client(entity, "accountant")
    res = client.post(
        "/api/v1/payroll-advances/",
        {
            "entity": str(entity.id),
            "employee": str(employee.id),
            "advance_date": "2026-06-01",
            "amount": "1200.00",
            "installments": 3,
            "advance_account": str(acct(STAFF_ADVANCES).id),
        },
        format="json",
    )
    advance_id = res.data["id"]
    res = client.post(f"/api/v1/payroll-advances/{advance_id}/pay/")
    assert res.status_code == 400


def test_advance_cannot_be_paid_twice(entity, employee, acct, bank_enbd):
    client = _client(entity, "accountant")
    res = client.post(
        "/api/v1/payroll-advances/",
        {
            "entity": str(entity.id),
            "employee": str(employee.id),
            "advance_date": "2026-06-01",
            "amount": "600.00",
            "installments": 1,
            "advance_account": str(acct(STAFF_ADVANCES).id),
            "bank_account": str(bank_enbd.id),
        },
        format="json",
    )
    advance_id = res.data["id"]
    first = client.post(f"/api/v1/payroll-advances/{advance_id}/pay/")
    assert first.status_code == 200, first.content
    second = client.post(f"/api/v1/payroll-advances/{advance_id}/pay/")
    assert second.status_code == 400


def test_advance_write_requires_role(entity, employee, acct):
    client = _client(entity, role=None)
    res = client.post(
        "/api/v1/payroll-advances/",
        {
            "entity": str(entity.id),
            "employee": str(employee.id),
            "advance_date": "2026-06-01",
            "amount": "600.00",
            "advance_account": str(acct(STAFF_ADVANCES).id),
        },
        format="json",
    )
    assert res.status_code == 403
