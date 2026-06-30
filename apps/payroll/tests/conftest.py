"""Shared fixtures for payroll tests."""

from datetime import date
from decimal import Decimal

import pytest

from apps.accounts.models import Account
from apps.accounts.services.seed import seed_entity_coa, seed_tax_codes
from apps.banking.models import BankAccount
from apps.core.models import Currency
from apps.ledger.models import AccountingPeriod
from apps.payroll.models import ComponentType, Employee, EmployeeSalary, SalaryComponent
from apps.tenants.models import BusinessCategory, Entity

BANK_ENBD = "101-100-110-010"
DRIVER_SALARY = "101-500-530-001"
ADMIN_SALARIES = "101-600-610-001"
SALARIES_PAYABLE = "101-200-240-001"
STAFF_ADVANCES = "101-100-120-003"
GRATUITY_PROVISION = "101-200-240-002"
GRATUITY_EXPENSE = "101-600-610-002"


@pytest.fixture
def entity(db):
    aed = Currency.objects.create(code="AED", name="UAE Dirham", symbol="AED", is_base=True)
    cat = BusinessCategory.objects.create(
        key="transport", label="Transport", band="1", coa_template_key="transport"
    )
    ent = Entity.objects.create(
        code="RGT",
        numeric_code="101",
        legal_name="Regency Transport LLC",
        category=cat,
        base_currency=aed,
    )
    seed_entity_coa(ent)
    seed_tax_codes(ent)
    AccountingPeriod.objects.create(
        entity=ent,
        fiscal_year=2026,
        period_no=6,
        name="Jun-2026",
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 30),
        status=AccountingPeriod.Status.OPEN,
    )
    return ent


def _acct(entity, code):
    return Account.objects.get(entity=entity, code=code)


@pytest.fixture
def acct(entity):
    return lambda code: _acct(entity, code)


@pytest.fixture
def bank_enbd(entity):
    return BankAccount.objects.create(
        entity=entity,
        code="ENBD",
        name="ENBD Current",
        gl_account=_acct(entity, BANK_ENBD),
        currency=entity.base_currency,
    )


@pytest.fixture
def components(entity):
    salary_acct = _acct(entity, DRIVER_SALARY)
    basic = SalaryComponent.objects.create(
        entity=entity,
        code="BASIC",
        name="Basic Salary",
        component_type=ComponentType.EARNING,
        is_gratuity_base=True,
        is_wps_fixed=True,
        account=salary_acct,
    )
    hra = SalaryComponent.objects.create(
        entity=entity,
        code="HRA",
        name="Housing Allowance",
        component_type=ComponentType.EARNING,
        is_gratuity_base=False,
        is_wps_fixed=False,
        account=salary_acct,
    )
    adv = SalaryComponent.objects.create(
        entity=entity,
        code="ADV",
        name="Advance Recovery",
        component_type=ComponentType.DEDUCTION,
        is_wps_fixed=False,
        account=_acct(entity, STAFF_ADVANCES),
    )
    return {"BASIC": basic, "HRA": hra, "ADV": adv}


def _employee(entity, code, **kw):
    defaults = {
        "name": f"Employee {code}",
        "join_date": date(2022, 6, 30),
        "pay_method": Employee.PayMethod.WPS,
        "mol_personal_no": f"MOL{code}",
        "bank_routing_code": "ENBDAEAD",
        "iban": f"AE07033123456789{code}",
        "payable_account": _acct(entity, SALARIES_PAYABLE),
    }
    defaults.update(kw)
    return Employee.objects.create(entity=entity, code=code, **defaults)


@pytest.fixture
def employee(entity, components):
    emp = _employee(entity, "E001")
    EmployeeSalary.objects.create(
        employee=emp,
        component=components["BASIC"],
        amount=Decimal("3000.00"),
        effective_from=date(2022, 6, 30),
    )
    EmployeeSalary.objects.create(
        employee=emp,
        component=components["HRA"],
        amount=Decimal("1000.00"),
        effective_from=date(2022, 6, 30),
    )
    return emp


@pytest.fixture
def make_employee(entity, components):
    def _make(code, basic, hra):
        emp = _employee(entity, code)
        EmployeeSalary.objects.create(
            employee=emp,
            component=components["BASIC"],
            amount=Decimal(basic),
            effective_from=date(2022, 6, 30),
        )
        EmployeeSalary.objects.create(
            employee=emp,
            component=components["HRA"],
            amount=Decimal(hra),
            effective_from=date(2022, 6, 30),
        )
        return emp

    return _make
