"""Driver receivable clearing: receipts, write-offs, allocation, and reversal.

A negative-net settlement books a receivable without touching cash. These tests
cover the other half — collecting it or writing it off — and the invariants that
keep the two halves consistent: allocation must equal the document, nothing may
be over-cleared, and reversing gives back exactly what was taken.
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from rest_framework.test import APIClient

import pytest

from apps.drivers.models import DriverClearing, DriverDocStatus, Settlement
from apps.ledger.models import EntryStatus
from apps.settings.services.driver_accounting import (
    provision_driver_accounting,
    set_driver_write_off_account,
)
from apps.tenants.models import UserEntityMembership

pytestmark = pytest.mark.django_db
User = get_user_model()

D = Decimal
ON = date(2026, 6, 15)
PERIOD_START = date(2026, 6, 1)
PERIOD_END = date(2026, 6, 30)

DRIVER_PAYOUT = "101-500-530-003"
STAFF_ADVANCES = "101-100-120-003"
SALIK = "101-500-510-001"
BAD_DEBTS = "101-700-730-002"


def _superuser():
    client = APIClient()
    client.force_authenticate(
        User.objects.create_superuser(email="root@example.com", password="pw")
    )
    return client


def _role_client(entity, role="accountant"):
    user = User.objects.create_user(email=f"{role}@example.com", password="pw")
    user.groups.add(Group.objects.get_or_create(name=role)[0])
    UserEntityMembership.objects.create(user=user, entity=entity)
    client = APIClient()
    client.force_authenticate(user)
    return client


def _owing_settlement(entity, driver, acct, bank, *, gross="1000", deduction="1500"):
    """Post a settlement whose deductions exceed gross, leaving a receivable."""
    settlement = Settlement.objects.create(
        entity=entity,
        driver=driver,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        settlement_date=ON,
        gross_amount=D(gross),
        gross_account=acct(DRIVER_PAYOUT),
        pay_account=bank,
        allows_negative_net=True,
    )
    settlement.deductions.create(kind="fine", account=acct(SALIK), amount=D(deduction))
    from apps.drivers.services.post import post_settlement

    post_settlement(settlement)
    settlement.refresh_from_db()
    return settlement


def _payload(entity, driver, settlement, *, amount, kind="receipt", bank=None, applied=None):
    body = {
        "entity": str(entity.id),
        "driver": str(driver.id),
        "kind": kind,
        "clearing_date": ON.isoformat(),
        "amount": amount,
        "lines": [{"settlement": str(settlement.id), "amount": applied or amount}],
    }
    if bank is not None:
        body["bank_account"] = str(bank.id)
    return body


# --- the settlement side seeds the receivable -------------------------------


def test_negative_net_settlement_seeds_the_outstanding_balance(entity, driver, bank_enbd, acct):
    settlement = _owing_settlement(entity, driver, acct, bank_enbd)
    assert settlement.net_amount == D("-500.00")
    assert settlement.receivable_balance == D("500.00")
    assert settlement.cleared_amount == D("0.00")


def test_positive_net_settlement_owes_nothing(entity, driver, bank_enbd, acct):
    settlement = _owing_settlement(entity, driver, acct, bank_enbd, gross="5000", deduction="100")
    assert settlement.net_amount == D("4900.00")
    assert settlement.receivable_balance == D("0.00")


def test_outstanding_endpoint_lists_only_what_is_owed(entity, driver, bank_enbd, acct):
    owing = _owing_settlement(entity, driver, acct, bank_enbd)
    _owing_settlement(entity, driver, acct, bank_enbd, gross="5000", deduction="100")
    client = _superuser()
    res = client.get(f"/api/v1/driver-settlements/outstanding/?driver={driver.id}")
    assert res.status_code == 200
    assert [row["id"] for row in res.data["settlements"]] == [str(owing.id)]

    missing = client.get("/api/v1/driver-settlements/outstanding/")
    assert missing.status_code == 400


# --- receipts ---------------------------------------------------------------


def test_receipt_posts_bank_debit_against_the_configured_receivable(
    entity, driver, bank_enbd, acct
):
    settlement = _owing_settlement(entity, driver, acct, bank_enbd)
    client = _superuser()
    created = client.post(
        "/api/v1/driver-clearings/",
        _payload(entity, driver, settlement, amount="500", bank=bank_enbd),
        format="json",
    )
    assert created.status_code == 201, created.content
    posted = client.post(f"/api/v1/driver-clearings/{created.data['id']}/post/", {}, format="json")
    assert posted.status_code == 200, posted.content
    assert posted.data["status"] == DriverDocStatus.POSTED
    assert posted.data["clearing_no"].startswith("DRCP-")

    clearing = DriverClearing.objects.get(id=created.data["id"])
    je = clearing.journal_entry
    assert je.status == EntryStatus.POSTED
    assert je.total_debit == je.total_credit == D("500.00")
    assert je.lines.get(account=bank_enbd.gl_account).debit == D("500.00")
    receivable_line = je.lines.get(account=acct(STAFF_ADVANCES))
    assert receivable_line.credit == D("500.00")
    assert receivable_line.driver_id == driver.id

    settlement.refresh_from_db()
    assert settlement.cleared_amount == D("500.00")
    assert settlement.receivable_balance == D("0.00")


def test_partial_receipt_leaves_the_remainder_outstanding(entity, driver, bank_enbd, acct):
    settlement = _owing_settlement(entity, driver, acct, bank_enbd)
    client = _superuser()
    created = client.post(
        "/api/v1/driver-clearings/",
        _payload(entity, driver, settlement, amount="200", bank=bank_enbd),
        format="json",
    )
    client.post(f"/api/v1/driver-clearings/{created.data['id']}/post/", {}, format="json")

    settlement.refresh_from_db()
    assert settlement.cleared_amount == D("200.00")
    assert settlement.receivable_balance == D("300.00")


def test_receipt_cannot_clear_more_than_is_outstanding(entity, driver, bank_enbd, acct):
    settlement = _owing_settlement(entity, driver, acct, bank_enbd)
    client = _superuser()
    created = client.post(
        "/api/v1/driver-clearings/",
        _payload(entity, driver, settlement, amount="600", bank=bank_enbd),
        format="json",
    )
    assert created.status_code == 201
    res = client.post(f"/api/v1/driver-clearings/{created.data['id']}/post/", {}, format="json")
    assert res.status_code == 400

    settlement.refresh_from_db()
    assert settlement.receivable_balance == D("500.00")  # untouched


def test_allocation_must_equal_the_clearing_amount(entity, driver, bank_enbd, acct):
    settlement = _owing_settlement(entity, driver, acct, bank_enbd)
    res = _superuser().post(
        "/api/v1/driver-clearings/",
        _payload(entity, driver, settlement, amount="500", bank=bank_enbd, applied="300"),
        format="json",
    )
    assert res.status_code == 400
    assert "lines" in res.data


def test_receipt_requires_a_bank_account(entity, driver, bank_enbd, acct):
    settlement = _owing_settlement(entity, driver, acct, bank_enbd)
    res = _superuser().post(
        "/api/v1/driver-clearings/",
        _payload(entity, driver, settlement, amount="500"),
        format="json",
    )
    assert res.status_code == 400
    assert "bank_account" in res.data


def test_cannot_clear_a_settlement_that_owes_nothing(entity, driver, bank_enbd, acct):
    settled = _owing_settlement(entity, driver, acct, bank_enbd, gross="5000", deduction="100")
    client = _superuser()
    created = client.post(
        "/api/v1/driver-clearings/",
        _payload(entity, driver, settled, amount="100", bank=bank_enbd),
        format="json",
    )
    assert created.status_code == 201
    res = client.post(f"/api/v1/driver-clearings/{created.data['id']}/post/", {}, format="json")
    assert res.status_code == 400


def test_cannot_clear_another_drivers_settlement(entity, driver, bank_enbd, acct):
    from apps.drivers.models import Driver

    settlement = _owing_settlement(entity, driver, acct, bank_enbd)
    other = Driver.objects.create(entity=entity, code="D999", name="Other Driver")
    res = _superuser().post(
        "/api/v1/driver-clearings/",
        _payload(entity, other, settlement, amount="500", bank=bank_enbd),
        format="json",
    )
    assert res.status_code == 400
    assert "lines" in res.data


def test_duplicate_post_rejected(entity, driver, bank_enbd, acct):
    settlement = _owing_settlement(entity, driver, acct, bank_enbd)
    client = _superuser()
    created = client.post(
        "/api/v1/driver-clearings/",
        _payload(entity, driver, settlement, amount="500", bank=bank_enbd),
        format="json",
    )
    first = client.post(f"/api/v1/driver-clearings/{created.data['id']}/post/", {}, format="json")
    assert first.status_code == 200
    again = client.post(f"/api/v1/driver-clearings/{created.data['id']}/post/", {}, format="json")
    assert again.status_code == 400


# --- write-offs -------------------------------------------------------------


def test_write_off_expenses_the_balance_without_touching_bank(entity, driver, bank_enbd, acct):
    set_driver_write_off_account(entity, acct(BAD_DEBTS))
    settlement = _owing_settlement(entity, driver, acct, bank_enbd)
    client = _superuser()
    created = client.post(
        "/api/v1/driver-clearings/",
        _payload(entity, driver, settlement, amount="500", kind="write_off"),
        format="json",
    )
    assert created.status_code == 201, created.content
    posted = client.post(f"/api/v1/driver-clearings/{created.data['id']}/post/", {}, format="json")
    assert posted.status_code == 200, posted.content
    assert posted.data["clearing_no"].startswith("DWO-")

    je = DriverClearing.objects.get(id=created.data["id"]).journal_entry
    assert je.total_debit == je.total_credit == D("500.00")
    assert je.lines.get(account=acct(BAD_DEBTS)).debit == D("500.00")
    assert je.lines.get(account=acct(STAFF_ADVANCES)).credit == D("500.00")
    # No money moved.
    assert not je.lines.filter(account=bank_enbd.gl_account).exists()

    settlement.refresh_from_db()
    assert settlement.receivable_balance == D("0.00")


def test_write_off_cannot_name_a_bank_account(entity, driver, bank_enbd, acct):
    set_driver_write_off_account(entity, acct(BAD_DEBTS))
    settlement = _owing_settlement(entity, driver, acct, bank_enbd)
    res = _superuser().post(
        "/api/v1/driver-clearings/",
        _payload(entity, driver, settlement, amount="500", kind="write_off", bank=bank_enbd),
        format="json",
    )
    assert res.status_code == 400
    assert "bank_account" in res.data


def test_write_off_refused_when_no_account_is_configured(entity, driver, bank_enbd, acct):
    from apps.settings.services.driver_accounting import get_config

    config = get_config(entity)
    config.default_write_off_account = None
    config.save(update_fields=["default_write_off_account"])

    settlement = _owing_settlement(entity, driver, acct, bank_enbd)
    client = _superuser()
    created = client.post(
        "/api/v1/driver-clearings/",
        _payload(entity, driver, settlement, amount="500", kind="write_off"),
        format="json",
    )
    assert created.status_code == 201
    res = client.post(f"/api/v1/driver-clearings/{created.data['id']}/post/", {}, format="json")
    assert res.status_code == 400
    settlement.refresh_from_db()
    assert settlement.receivable_balance == D("500.00")


def test_provisioning_configures_the_write_off_account(entity, acct):
    config = provision_driver_accounting(entity)
    assert config.default_write_off_account_id == acct(BAD_DEBTS).id


# --- reversal ---------------------------------------------------------------


def _post_receipt(client, entity, driver, settlement, bank, amount="500"):
    created = client.post(
        "/api/v1/driver-clearings/",
        _payload(entity, driver, settlement, amount=amount, bank=bank),
        format="json",
    )
    assert created.status_code == 201, created.content
    posted = client.post(f"/api/v1/driver-clearings/{created.data['id']}/post/", {}, format="json")
    assert posted.status_code == 200, posted.content
    return created.data["id"]


def test_reversal_restores_the_outstanding_balance(entity, driver, bank_enbd, acct):
    settlement = _owing_settlement(entity, driver, acct, bank_enbd)
    client = _superuser()
    clearing_id = _post_receipt(client, entity, driver, settlement, bank_enbd)

    settlement.refresh_from_db()
    assert settlement.receivable_balance == D("0.00")

    res = client.post(f"/api/v1/driver-clearings/{clearing_id}/reverse/", {}, format="json")
    assert res.status_code == 200, res.content
    assert res.data["status"] == DriverDocStatus.REVERSED

    settlement.refresh_from_db()
    assert settlement.cleared_amount == D("0.00")
    assert settlement.receivable_balance == D("500.00")


def test_reversal_writes_a_mirror_entry_and_never_deletes(entity, driver, bank_enbd, acct):
    settlement = _owing_settlement(entity, driver, acct, bank_enbd)
    client = _superuser()
    clearing_id = _post_receipt(client, entity, driver, settlement, bank_enbd)
    original = DriverClearing.objects.get(id=clearing_id).journal_entry

    client.post(f"/api/v1/driver-clearings/{clearing_id}/reverse/", {}, format="json")

    original.refresh_from_db()
    assert original.status == EntryStatus.REVERSED
    mirror = original.reversed_by
    assert mirror is not None and mirror.status == EntryStatus.POSTED
    assert mirror.total_debit == mirror.total_credit == D("500.00")
    # The mirror swaps sides: the receivable is debited back.
    assert mirror.lines.get(account=acct(STAFF_ADVANCES)).debit == D("500.00")


def test_a_reversed_clearing_frees_the_balance_to_be_cleared_again(entity, driver, bank_enbd, acct):
    settlement = _owing_settlement(entity, driver, acct, bank_enbd)
    client = _superuser()
    clearing_id = _post_receipt(client, entity, driver, settlement, bank_enbd)
    client.post(f"/api/v1/driver-clearings/{clearing_id}/reverse/", {}, format="json")

    _post_receipt(client, entity, driver, settlement, bank_enbd)
    settlement.refresh_from_db()
    assert settlement.receivable_balance == D("0.00")


def test_cannot_reverse_a_draft(entity, driver, bank_enbd, acct):
    settlement = _owing_settlement(entity, driver, acct, bank_enbd)
    client = _superuser()
    created = client.post(
        "/api/v1/driver-clearings/",
        _payload(entity, driver, settlement, amount="500", bank=bank_enbd),
        format="json",
    )
    res = client.post(f"/api/v1/driver-clearings/{created.data['id']}/reverse/", {}, format="json")
    assert res.status_code == 400


def test_reversal_needs_manager_or_admin(entity, driver, bank_enbd, acct):
    """Reversing puts a receivable back on the books, so it is not everyday entry."""
    settlement = _owing_settlement(entity, driver, acct, bank_enbd)
    clearing_id = _post_receipt(_superuser(), entity, driver, settlement, bank_enbd)

    accountant = _role_client(entity, "accountant")
    denied = accountant.post(f"/api/v1/driver-clearings/{clearing_id}/reverse/", {}, format="json")
    assert denied.status_code == 403

    manager = _role_client(entity, "manager")
    allowed = manager.post(f"/api/v1/driver-clearings/{clearing_id}/reverse/", {}, format="json")
    assert allowed.status_code == 200


# --- configuration ----------------------------------------------------------


def test_clearing_refused_when_the_receivable_account_is_unconfigured(
    entity, driver, bank_enbd, acct
):
    from apps.settings.models import DriverAccountingConfig

    settlement = _owing_settlement(entity, driver, acct, bank_enbd)
    client = _superuser()
    created = client.post(
        "/api/v1/driver-clearings/",
        _payload(entity, driver, settlement, amount="500", bank=bank_enbd),
        format="json",
    )
    DriverAccountingConfig.all_objects.filter(entity=entity).hard_delete()

    res = client.post(f"/api/v1/driver-clearings/{created.data['id']}/post/", {}, format="json")
    assert res.status_code == 400
    settlement.refresh_from_db()
    assert settlement.receivable_balance == D("500.00")


def test_clearing_credits_the_configured_account_even_if_it_changes_later(
    entity, driver, bank_enbd, acct
):
    """The clearing records what it actually used, so history cannot be rewritten."""
    from apps.settings.services.driver_accounting import set_driver_receivable_account

    settlement = _owing_settlement(entity, driver, acct, bank_enbd)
    client = _superuser()
    clearing_id = _post_receipt(client, entity, driver, settlement, bank_enbd)

    set_driver_receivable_account(entity, acct("101-100-120-006"))

    clearing = DriverClearing.objects.get(id=clearing_id)
    assert clearing.receivable_account_id == acct(STAFF_ADVANCES).id
    assert clearing.journal_entry.lines.filter(account=acct(STAFF_ADVANCES)).exists()


# --- entity isolation & permissions -----------------------------------------


def test_clearings_are_entity_scoped(entity, driver, bank_enbd, acct):
    settlement = _owing_settlement(entity, driver, acct, bank_enbd)
    _post_receipt(_superuser(), entity, driver, settlement, bank_enbd)

    outsider = User.objects.create_user(email="outsider@example.com", password="pw")
    outsider.groups.add(Group.objects.get_or_create(name="accountant")[0])
    client = APIClient()
    client.force_authenticate(outsider)
    res = client.get("/api/v1/driver-clearings/")
    assert res.status_code == 200
    assert res.data["results"] == []


def test_clearing_delete_is_not_exposed(entity, driver, bank_enbd, acct):
    settlement = _owing_settlement(entity, driver, acct, bank_enbd)
    client = _superuser()
    clearing_id = _post_receipt(client, entity, driver, settlement, bank_enbd)
    res = client.delete(f"/api/v1/driver-clearings/{clearing_id}/")
    assert res.status_code == 405


def test_backfill_seeds_outstanding_on_pre_existing_settlements(entity, driver, bank_enbd, acct):
    """Settlements posted before clearing existed must not read as fully settled."""
    from importlib import import_module

    from django.apps import apps as django_apps

    migration = import_module("apps.drivers.migrations.0006_backfill_settlement_receivable_balance")
    settlement = _owing_settlement(entity, driver, acct, bank_enbd)
    # Rewind to the pre-migration shape: posted, negative net, nothing tracked.
    Settlement.objects.filter(id=settlement.id).update(
        cleared_amount=D("0.00"), receivable_balance=D("0.00")
    )

    migration.backfill(django_apps, None)

    settlement.refresh_from_db()
    assert settlement.receivable_balance == D("500.00")


def test_backfill_leaves_settled_settlements_alone(entity, driver, bank_enbd, acct):
    from importlib import import_module

    from django.apps import apps as django_apps

    migration = import_module("apps.drivers.migrations.0006_backfill_settlement_receivable_balance")
    settlement = _owing_settlement(entity, driver, acct, bank_enbd)
    _post_receipt(_superuser(), entity, driver, settlement, bank_enbd)

    migration.backfill(django_apps, None)

    settlement.refresh_from_db()
    assert settlement.cleared_amount == D("500.00")
    assert settlement.receivable_balance == D("0.00")
