"""Driver accounting configuration: eligibility rules, provisioning, and API.

The configured FK is the only thing that authorises a driver receivable posting,
so these tests are the gate: what may be configured, what provisioning does on a
freshly seeded entity, and who may change it.
"""

import re
from importlib import import_module

from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from rest_framework.test import APIClient

import pytest

from apps.accounts.models import Account
from apps.accounts.services.seed import seed_entity_coa
from apps.core.models import Currency
from apps.settings.models import DriverAccountingConfig
from apps.settings.services.driver_accounting import (
    DriverAccountingConfigError,
    find_provisionable_account,
    get_config,
    provision_driver_accounting,
    resolve_receivable_account,
    set_driver_receivable_account,
    validate_receivable_account,
)
from apps.tenants.models import BusinessCategory, Entity, UserEntityMembership

pytestmark = pytest.mark.django_db
User = get_user_model()

STAFF_ADVANCES = "101-100-120-003"
BANK_ENBD = "101-100-110-010"
TRADE_RECEIVABLES = "101-100-120-001"


def _entity(code="RGT", numeric="101", **kwargs):
    aed = Currency.objects.filter(code="AED").first() or Currency.objects.create(
        code="AED", name="UAE Dirham", symbol="AED", is_base=True
    )
    cat = BusinessCategory.objects.filter(key="transport").first() or (
        BusinessCategory.objects.create(
            key="transport", label="Transport", band="1", coa_template_key="transport"
        )
    )
    ent = Entity.objects.create(
        code=code,
        numeric_code=numeric,
        legal_name=f"{code} LLC",
        category=cat,
        base_currency=aed,
        **kwargs,
    )
    seed_entity_coa(ent)
    return ent


@pytest.fixture
def entity(db):
    return _entity()


@pytest.fixture
def acct(entity):
    return lambda code: Account.objects.get(entity=entity, code=code)


def _client(entity, role=None, *, member=True, superuser=False):
    if superuser:
        user = User.objects.create_superuser(email="root@example.com", password="pw")
    else:
        user = User.objects.create_user(email=f"{role or 'member'}@example.com", password="pw")
        if role:
            user.groups.add(Group.objects.get_or_create(name=role)[0])
        if member:
            UserEntityMembership.objects.create(user=user, entity=entity)
    client = APIClient()
    client.force_authenticate(user)
    return client


# --- eligibility matrix -----------------------------------------------------


def test_seeded_staff_advances_is_eligible(entity, acct):
    account = acct(STAFF_ADVANCES)
    assert validate_receivable_account(entity, account) is account
    # It qualifies through configuration, not through its type.
    assert account.account_type == Account.AccountType.GENERAL


def test_rejects_missing_account(entity):
    with pytest.raises(DriverAccountingConfigError, match="required"):
        validate_receivable_account(entity, None)


def test_rejects_account_from_another_entity(entity, acct):
    other = _entity(code="ACE", numeric="102")
    foreign = Account.objects.get(entity=other, code=STAFF_ADVANCES.replace("101", "102", 1))
    with pytest.raises(DriverAccountingConfigError, match="different entity"):
        validate_receivable_account(entity, foreign)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("is_active", False, "active"),
        ("is_postable", False, "postable"),
        ("allow_manual_posting", False, "manual posting"),
        ("is_bank_account", True, "bank, cash, or fixed-asset"),
        ("is_control_account", True, "control account"),
        ("subledger", "customer", "subledger"),
        ("normal_balance", "C", "debit-normal"),
    ],
)
def test_rejects_ineligible_flag(entity, acct, field, value, message):
    account = acct(STAFF_ADVANCES)
    setattr(account, field, value)
    account.save(update_fields=[field])
    with pytest.raises(DriverAccountingConfigError, match=message):
        validate_receivable_account(entity, account)


@pytest.mark.parametrize(
    "account_type",
    [Account.AccountType.BANK, Account.AccountType.CASH, Account.AccountType.FIXED_ASSET],
)
def test_rejects_forbidden_account_types(entity, acct, account_type):
    account = acct(STAFF_ADVANCES)
    account.account_type = account_type
    account.save(update_fields=["account_type"])
    with pytest.raises(DriverAccountingConfigError, match="bank, cash, or fixed-asset"):
        validate_receivable_account(entity, account)


def test_rejects_non_asset_account(entity):
    # Eligible in every other respect, so nature is what trips it.
    liability = Account.objects.filter(
        entity=entity,
        sub_group__nature="liability",
        is_active=True,
        is_postable=True,
        allow_manual_posting=True,
    ).first()
    assert liability is not None
    with pytest.raises(DriverAccountingConfigError, match="asset account"):
        validate_receivable_account(entity, liability)


def test_rejects_bank_gl_account(entity, acct):
    with pytest.raises(DriverAccountingConfigError, match="bank, cash, or fixed-asset"):
        validate_receivable_account(entity, acct(BANK_ENBD))


def test_set_account_validates_before_writing(entity, acct):
    account = acct(BANK_ENBD)
    with pytest.raises(DriverAccountingConfigError):
        set_driver_receivable_account(entity, account)
    assert not DriverAccountingConfig.objects.filter(entity=entity).exists()


def test_set_account_is_idempotent_and_updates(entity, acct):
    first = set_driver_receivable_account(entity, acct(STAFF_ADVANCES))
    other = Account.objects.filter(
        entity=entity,
        sub_group__nature="asset",
        normal_balance="D",
        is_postable=True,
        is_control_account=False,
        subledger="",
        allow_manual_posting=True,
        is_bank_account=False,
        account_type=Account.AccountType.GENERAL,
    ).exclude(id=first.default_receivable_account_id)[0]
    second = set_driver_receivable_account(entity, other)
    assert second.id == first.id
    assert DriverAccountingConfig.objects.filter(entity=entity).count() == 1
    assert second.default_receivable_account_id == other.id


def test_reconfiguring_after_a_soft_delete_revives_the_row(entity, acct):
    """The hidden row keeps the entity's unique key, so writing must revive it."""
    original = set_driver_receivable_account(entity, acct(STAFF_ADVANCES))
    original.delete()  # soft delete
    assert get_config(entity) is None

    revived = set_driver_receivable_account(entity, acct("101-100-120-006"))
    assert revived.id == original.id
    assert DriverAccountingConfig.all_objects.filter(entity=entity).count() == 1
    assert get_config(entity).default_receivable_account_id == acct("101-100-120-006").id


def test_provisioning_revives_a_soft_deleted_configuration(entity, acct):
    set_driver_receivable_account(entity, acct(STAFF_ADVANCES)).delete()
    config = provision_driver_accounting(entity)
    assert config is not None
    assert config.default_receivable_account_id == acct(STAFF_ADVANCES).id
    assert DriverAccountingConfig.all_objects.filter(entity=entity).count() == 1


def test_configured_account_is_protected_from_deletion(entity, acct):
    """PROTECT, so a configured account cannot be removed out from under posting."""
    from django.db.models import ProtectedError

    set_driver_receivable_account(entity, acct(STAFF_ADVANCES))
    with pytest.raises(ProtectedError):
        acct(STAFF_ADVANCES).hard_delete()


# --- resolution -------------------------------------------------------------


def test_resolve_reports_missing_configuration(entity):
    with pytest.raises(
        DriverAccountingConfigError,
        match=re.escape("Driver Receivable account is not configured for this entity."),
    ):
        resolve_receivable_account(entity)


def test_resolve_returns_configured_account(entity, acct):
    set_driver_receivable_account(entity, acct(STAFF_ADVANCES))
    assert resolve_receivable_account(entity).id == acct(STAFF_ADVANCES).id


# --- provisioning -----------------------------------------------------------


def test_provisioning_finds_account_without_hardcoded_code(entity, acct):
    # Identified by characteristics, so it resolves for any entity number.
    assert find_provisionable_account(entity).id == acct(STAFF_ADVANCES).id


def test_provisioning_configures_seeded_entity(entity, acct):
    config = provision_driver_accounting(entity)
    assert config is not None
    assert config.default_receivable_account_id == acct(STAFF_ADVANCES).id


def test_provisioning_is_idempotent(entity):
    first = provision_driver_accounting(entity)
    second = provision_driver_accounting(entity)
    assert first.id == second.id
    assert DriverAccountingConfig.objects.filter(entity=entity).count() == 1


def test_provisioning_never_overwrites_a_deliberate_choice(entity, acct):
    chosen = Account.objects.filter(
        entity=entity,
        sub_group__nature="asset",
        normal_balance="D",
        is_postable=True,
        is_control_account=False,
        subledger="",
        allow_manual_posting=True,
        is_bank_account=False,
        account_type=Account.AccountType.GENERAL,
    ).exclude(code=STAFF_ADVANCES)[0]
    set_driver_receivable_account(entity, chosen)
    assert provision_driver_accounting(entity).default_receivable_account_id == chosen.id


def test_provisioning_declines_when_no_match(entity, acct):
    account = acct(STAFF_ADVANCES)
    account.name = "Employee Loans"
    account.save(update_fields=["name"])
    assert find_provisionable_account(entity) is None
    assert provision_driver_accounting(entity) is None
    assert get_config(entity) is None


def test_provisioning_declines_when_ambiguous(entity, acct):
    """Two accounts fit the markers, so provisioning refuses to pick one."""
    from apps.accounts.models import AccountGroup

    original = acct(STAFF_ADVANCES)
    # A second receivables sub-group under a different main group — the account
    # uniqueness key is (entity, sub_group, charge_segment), so this is the only
    # way to get a genuine duplicate.
    main = AccountGroup.objects.create(
        entity=entity, level=1, segment="190", code="101-190", name="Other Assets", nature="asset"
    )
    sub = AccountGroup.objects.create(
        entity=entity,
        level=2,
        segment="120",
        parent=main,
        code="101-190-120",
        name="Other Receivables",
        nature="asset",
    )
    Account.objects.create(
        entity=entity,
        sub_group=sub,
        charge_segment="003",
        code="101-190-120-003",
        name="Staff Advances",
        account_type=original.account_type,
        normal_balance="D",
        is_postable=True,
        allow_manual_posting=True,
    )
    assert find_provisionable_account(entity) is None
    assert provision_driver_accounting(entity) is None
    assert get_config(entity) is None


def test_seed_command_provisions_configuration(db, capsys):
    from django.core.management import call_command

    ent = _entity(code="SEED", numeric="103")
    DriverAccountingConfig.objects.filter(entity=ent).delete()
    call_command("seed_coa", entity="103")
    config = get_config(ent)
    assert config is not None
    assert config.default_receivable_account.name == "Staff Advances"
    assert "driver receivable 103-100-120-003" in capsys.readouterr().out


# --- backfill migration -----------------------------------------------------
#
# Exercised against the live app registry. The migration keeps its own literal
# copy of the markers on purpose (migrations must not drift with the service),
# so these tests are what catches that copy drifting from the seeded chart of
# accounts.

_MIGRATION = import_module("apps.settings.migrations.0004_backfill_driver_accounting_config")


def test_backfill_markers_still_match_the_seeded_account(entity):
    matches = list(Account.objects.filter(entity=entity, **_MIGRATION.STAFF_ADVANCE_MARKERS))
    assert [a.code for a in matches] == [STAFF_ADVANCES]


def test_backfill_configures_existing_entities(entity, acct):
    # hard_delete: the migration runs against a table created moments earlier,
    # so an empty table — not soft-deleted rows — is the faithful starting point.
    DriverAccountingConfig.all_objects.all().hard_delete()
    _MIGRATION.backfill(django_apps, None)
    assert get_config(entity).default_receivable_account_id == acct(STAFF_ADVANCES).id


def test_backfill_is_idempotent(entity):
    # hard_delete: the migration runs against a table created moments earlier,
    # so an empty table — not soft-deleted rows — is the faithful starting point.
    DriverAccountingConfig.all_objects.all().hard_delete()
    _MIGRATION.backfill(django_apps, None)
    first = get_config(entity)
    _MIGRATION.backfill(django_apps, None)
    assert DriverAccountingConfig.objects.filter(entity=entity).count() == 1
    assert get_config(entity).id == first.id


def test_backfill_never_repoints_an_existing_configuration(entity, acct):
    chosen = Account.objects.get(entity=entity, code="101-100-120-006")
    set_driver_receivable_account(entity, chosen)
    _MIGRATION.backfill(django_apps, None)
    assert get_config(entity).default_receivable_account_id == chosen.id


def test_backfill_skips_entities_without_an_unambiguous_match(entity, acct):
    # hard_delete: the migration runs against a table created moments earlier,
    # so an empty table — not soft-deleted rows — is the faithful starting point.
    DriverAccountingConfig.all_objects.all().hard_delete()
    account = acct(STAFF_ADVANCES)
    account.is_postable = False
    account.save(update_fields=["is_postable"])
    _MIGRATION.backfill(django_apps, None)
    assert get_config(entity) is None


def test_backfill_reverse_removes_only_its_own_rows(entity, acct):
    other = _entity(code="ACE", numeric="102")
    # hard_delete: the migration runs against a table created moments earlier,
    # so an empty table — not soft-deleted rows — is the faithful starting point.
    DriverAccountingConfig.all_objects.all().hard_delete()
    _MIGRATION.backfill(django_apps, None)
    # A hand-picked account is not something the migration could have created.
    set_driver_receivable_account(
        entity, Account.objects.get(entity=entity, code="101-100-120-006")
    )

    _MIGRATION.unbackfill(django_apps, None)
    assert get_config(other) is None
    assert get_config(entity) is not None


# --- API --------------------------------------------------------------------


def test_member_can_read_configuration(entity, acct):
    set_driver_receivable_account(entity, acct(STAFF_ADVANCES))
    res = _client(entity, role="accountant").get(
        f"/api/v1/driver-accounting-config/?entity={entity.id}"
    )
    assert res.status_code == 200
    row = res.data["results"][0]
    assert str(row["default_receivable_account"]) == str(acct(STAFF_ADVANCES).id)
    assert row["account_code"] == STAFF_ADVANCES
    assert row["account_name"] == "Staff Advances"


def test_read_is_scoped_to_accessible_entities(entity, acct):
    other = _entity(code="ACE", numeric="102")
    set_driver_receivable_account(entity, acct(STAFF_ADVANCES))
    set_driver_receivable_account(other, Account.objects.get(entity=other, code="102-100-120-003"))
    res = _client(entity, role="accountant").get("/api/v1/driver-accounting-config/")
    assert res.status_code == 200
    assert [str(r["entity"]) for r in res.data["results"]] == [str(entity.id)]


def test_unconfigured_entity_returns_empty(entity):
    res = _client(entity, role="accountant").get("/api/v1/driver-accounting-config/")
    assert res.status_code == 200
    assert res.data["results"] == []


def test_accountant_cannot_write_configuration(entity, acct):
    res = _client(entity, role="accountant").post(
        "/api/v1/driver-accounting-config/",
        {"entity": str(entity.id), "default_receivable_account": str(acct(STAFF_ADVANCES).id)},
        format="json",
    )
    assert res.status_code == 403


def test_manager_can_write_configuration(entity, acct):
    res = _client(entity, role="manager").post(
        "/api/v1/driver-accounting-config/",
        {"entity": str(entity.id), "default_receivable_account": str(acct(STAFF_ADVANCES).id)},
        format="json",
    )
    assert res.status_code == 201, res.content
    assert get_config(entity).default_receivable_account_id == acct(STAFF_ADVANCES).id


def test_api_rejects_ineligible_account_with_field_error(entity, acct):
    res = _client(entity, role="manager").post(
        "/api/v1/driver-accounting-config/",
        {"entity": str(entity.id), "default_receivable_account": str(acct(BANK_ENBD).id)},
        format="json",
    )
    assert res.status_code == 400
    assert "default_receivable_account" in res.data


def test_api_rejects_second_configuration_for_an_entity(entity, acct):
    client = _client(entity, role="manager")
    payload = {
        "entity": str(entity.id),
        "default_receivable_account": str(acct(STAFF_ADVANCES).id),
    }
    assert (
        client.post("/api/v1/driver-accounting-config/", payload, format="json").status_code == 201
    )
    again = client.post("/api/v1/driver-accounting-config/", payload, format="json")
    assert again.status_code == 400
    assert "entity" in again.data


def test_delete_is_not_exposed(entity, acct):
    config = set_driver_receivable_account(entity, acct(STAFF_ADVANCES))
    res = _client(entity, superuser=True).delete(f"/api/v1/driver-accounting-config/{config.id}/")
    assert res.status_code == 405


# --- regression: customer AR still means AccountType.RECEIVABLE -------------


def test_receivable_account_type_still_marks_customer_ar(entity):
    """Option 2 reclassified nothing: RECEIVABLE remains the customer-AR control
    account, and Staff Advances remains a plain GENERAL asset."""
    debtors = Account.objects.get(entity=entity, code=TRADE_RECEIVABLES)
    assert debtors.account_type == Account.AccountType.RECEIVABLE
    assert debtors.is_control_account and debtors.subledger == "customer"
    assert (
        Account.objects.filter(entity=entity, account_type=Account.AccountType.RECEIVABLE).count()
        == 1
    )

    staff = Account.objects.get(entity=entity, code=STAFF_ADVANCES)
    assert staff.account_type == Account.AccountType.GENERAL
    assert not staff.is_control_account and staff.subledger == ""
