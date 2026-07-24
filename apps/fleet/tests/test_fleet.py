"""Fleet tests: EMI split posting, depreciation run (vehicle dim), expiry alerts."""

from datetime import date
from decimal import Decimal

import pytest

from apps.fleet.models import (
    DepreciationRun,
    FleetDocStatus,
    VehicleDocument,
    VehicleLoanInstallment,
)
from apps.fleet.services.alerts import expiring_documents
from apps.fleet.services.post import FleetError, post_depreciation_run, post_emi
from apps.ledger.models import EntryStatus

pytestmark = pytest.mark.django_db

D = Decimal
ON = date(2026, 6, 15)
VEHICLE_LOAN = "101-200-220-001"
LOAN_INTEREST = "101-700-710-001"
VEHICLE_DEP_EXPENSE = "101-600-630-003"
VEHICLE_ACCUM_DEP = "101-100-150-002"


def test_emi_splits_principal_and_interest(entity, loan, bank_enbd, acct, vehicle):
    emi = VehicleLoanInstallment.objects.create(
        loan=loan,
        installment_no=1,
        due_date=ON,
        principal_component=D("800"),
        interest_component=D("200"),
        bank_account=bank_enbd,
    )
    post_emi(emi)
    emi.refresh_from_db()

    assert emi.status == FleetDocStatus.POSTED
    assert emi.total_amount == D("1000.00")
    je = emi.journal_entry
    assert je.status == EntryStatus.POSTED
    loan_line = je.lines.get(account=acct(VEHICLE_LOAN))
    assert loan_line.debit == D("800.00")
    assert loan_line.vehicle_id == vehicle.id  # profitability dimension carried
    assert je.lines.get(account=acct(LOAN_INTEREST)).debit == D("200.00")
    assert je.lines.get(account=bank_enbd.gl_account).credit == D("1000.00")
    assert je.total_debit == je.total_credit == D("1000.00")


def test_depreciation_run_posts_per_vehicle(entity, vehicle, acct):
    run = DepreciationRun.objects.create(entity=entity, run_date=ON, period_label="Jun-2026")
    post_depreciation_run(run)
    run.refresh_from_db()

    assert run.status == FleetDocStatus.POSTED
    assert run.run_no.startswith("DEP-")
    assert run.total_amount == D("2000.00")
    assert run.lines.count() == 1
    je = run.journal_entry
    dep_line = je.lines.get(account=acct(VEHICLE_DEP_EXPENSE))
    assert dep_line.debit == D("2000.00")
    assert dep_line.vehicle_id == vehicle.id
    assert je.lines.get(account=acct(VEHICLE_ACCUM_DEP)).credit == D("2000.00")


def test_depreciation_run_no_vehicles_rejected(entity, vehicle):
    vehicle.useful_life_months = None  # no depreciation configured
    vehicle.save(update_fields=["useful_life_months"])
    run = DepreciationRun.objects.create(entity=entity, run_date=ON)
    with pytest.raises(FleetError):
        post_depreciation_run(run)


def test_document_expiry_alerts(entity, vehicle):
    VehicleDocument.objects.create(
        vehicle=vehicle,
        doc_type=VehicleDocument.DocType.INSURANCE,
        expiry_date=date(2026, 7, 1),
    )
    VehicleDocument.objects.create(
        vehicle=vehicle,
        doc_type=VehicleDocument.DocType.REGISTRATION,
        expiry_date=date(2027, 1, 1),
    )
    soon = expiring_documents(entity, within_days=30, as_of=date(2026, 6, 15))
    assert [d.doc_type for d in soon] == ["insurance"]  # only the July expiry is within 30 days
