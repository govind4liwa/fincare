"""API tests for driver advances and settlements.

Covers the posting rules (balanced JE, gross/deduction mapping, negative net),
advance recovery and its guards, duplicate-post protection, entity isolation,
permissions, and payload validation.
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from rest_framework.test import APIClient

import pytest

from apps.accounts.models import Account
from apps.accounts.services.seed import seed_entity_coa
from apps.drivers.models import Advance, DriverDocStatus, Settlement
from apps.ledger.models import EntryStatus
from apps.tenants.models import Entity, UserEntityMembership

pytestmark = pytest.mark.django_db
User = get_user_model()

D = Decimal
ON = date(2026, 6, 15)
PERIOD_START = date(2026, 6, 1)
PERIOD_END = date(2026, 6, 30)

DRIVER_PAYOUT = "101-500-530-003"
DRIVER_COMMISSION = "101-500-530-002"
STAFF_ADVANCES = "101-100-120-003"
SALIK = "101-500-510-001"

UNSET = object()


def _superuser():
    client = APIClient()
    client.force_authenticate(
        User.objects.create_superuser(email="root@example.com", password="pw")
    )
    return client


def _role_client(entity, role="accountant", *, member=True):
    user = User.objects.create_user(email=f"{role}@example.com", password="pw")
    user.groups.add(Group.objects.get_or_create(name=role)[0])
    if member:
        UserEntityMembership.objects.create(user=user, entity=entity)
    client = APIClient()
    client.force_authenticate(user)
    return client


def _advance_payload(entity, driver, acct, bank, amount="1000"):
    return {
        "entity": str(entity.id),
        "driver": str(driver.id),
        "advance_date": ON.isoformat(),
        "amount": amount,
        "advance_account": str(acct(STAFF_ADVANCES).id),
        "bank_account": str(bank.id),
    }


def _settlement_payload(
    entity,
    driver,
    acct,
    bank,
    *,
    gross="5000",
    deductions=None,
    negative=False,
    receivable=UNSET,
):
    payload = {
        "entity": str(entity.id),
        "driver": str(driver.id),
        "period_start": PERIOD_START.isoformat(),
        "period_end": PERIOD_END.isoformat(),
        "settlement_date": ON.isoformat(),
        "gross_amount": gross,
        "gross_account": str(acct(DRIVER_PAYOUT).id),
        "pay_account": str(bank.id),
        "allows_negative_net": negative,
        "deductions": deductions if deductions is not None else [],
    }
    # Default the receivable account on the negative path so callers only pass it
    # when they are testing the account itself.
    if receivable is UNSET:
        if negative:
            payload["driver_receivable_account"] = str(acct(STAFF_ADVANCES).id)
    elif receivable is not None:
        payload["driver_receivable_account"] = receivable
    return payload


def _post_advance(client, entity, driver, acct, bank, amount="1000"):
    created = client.post(
        "/api/v1/driver-advances/",
        _advance_payload(entity, driver, acct, bank, amount),
        format="json",
    )
    assert created.status_code == 201, created.content
    posted = client.post(f"/api/v1/driver-advances/{created.data['id']}/post/", {}, format="json")
    assert posted.status_code == 200, posted.content
    return posted.data


# --- advances ---------------------------------------------------------------


def test_advance_create_and_post(entity, driver, bank_enbd, acct):
    client = _superuser()
    created = client.post(
        "/api/v1/driver-advances/", _advance_payload(entity, driver, acct, bank_enbd), format="json"
    )
    assert created.status_code == 201, created.content
    assert created.data["status"] == DriverDocStatus.DRAFT
    assert created.data["advance_no"] == ""

    posted = client.post(f"/api/v1/driver-advances/{created.data['id']}/post/", {}, format="json")
    assert posted.status_code == 200, posted.content
    assert posted.data["status"] == DriverDocStatus.POSTED
    assert posted.data["advance_no"].startswith("ADV-")
    assert posted.data["balance"] == "1000.00"

    advance = Advance.objects.get(id=created.data["id"])
    je = advance.journal_entry
    assert je.status == EntryStatus.POSTED
    assert je.total_debit == je.total_credit == D("1000.00")
    assert je.lines.get(account=acct(STAFF_ADVANCES)).debit == D("1000.00")
    assert je.lines.get(account=bank_enbd.gl_account).credit == D("1000.00")


def test_advance_duplicate_post_rejected(entity, driver, bank_enbd, acct):
    client = _superuser()
    advance = _post_advance(client, entity, driver, acct, bank_enbd)
    again = client.post(f"/api/v1/driver-advances/{advance['id']}/post/", {}, format="json")
    assert again.status_code == 400


def test_advance_rejects_non_positive_amount(entity, driver, bank_enbd, acct):
    res = _superuser().post(
        "/api/v1/driver-advances/",
        _advance_payload(entity, driver, acct, bank_enbd, amount="0"),
        format="json",
    )
    assert res.status_code == 400
    assert "amount" in res.data


def test_outstanding_advances_endpoint(entity, driver, bank_enbd, acct):
    client = _superuser()
    _post_advance(client, entity, driver, acct, bank_enbd, amount="1500")
    res = client.get(f"/api/v1/driver-advances/outstanding/?driver={driver.id}")
    assert res.status_code == 200
    assert [a["balance"] for a in res.data["advances"]] == ["1500.00"]

    missing = client.get("/api/v1/driver-advances/outstanding/")
    assert missing.status_code == 400


# --- settlements ------------------------------------------------------------


def test_settlement_posts_balanced_with_deductions(entity, driver, bank_enbd, acct):
    client = _superuser()
    payload = _settlement_payload(
        entity,
        driver,
        acct,
        bank_enbd,
        gross="5000",
        deductions=[
            {"kind": "commission", "account": str(acct(DRIVER_COMMISSION).id), "amount": "500"},
            {"kind": "salik", "account": str(acct(SALIK).id), "amount": "150"},
        ],
    )
    created = client.post("/api/v1/driver-settlements/", payload, format="json")
    assert created.status_code == 201, created.content
    assert created.data["status"] == DriverDocStatus.DRAFT
    assert len(created.data["deductions"]) == 2

    posted = client.post(
        f"/api/v1/driver-settlements/{created.data['id']}/post/", {}, format="json"
    )
    assert posted.status_code == 200, posted.content
    assert posted.data["status"] == DriverDocStatus.POSTED
    assert posted.data["settlement_no"].startswith("SETL-")
    assert posted.data["total_deductions"] == "650.00"
    assert posted.data["net_amount"] == "4350.00"

    je = Settlement.objects.get(id=created.data["id"]).journal_entry
    assert je.status == EntryStatus.POSTED
    assert je.total_debit == je.total_credit == D("5000.00")
    gross_line = je.lines.get(account=acct(DRIVER_PAYOUT))
    assert gross_line.debit == D("5000.00")
    assert gross_line.driver_id == driver.id  # profitability dimension
    assert je.lines.get(account=acct(DRIVER_COMMISSION)).credit == D("500.00")
    assert je.lines.get(account=acct(SALIK)).credit == D("150.00")
    assert je.lines.get(account=bank_enbd.gl_account).credit == D("4350.00")


def test_deductions_exceeding_gross_rejected_by_default(entity, driver, bank_enbd, acct):
    client = _superuser()
    payload = _settlement_payload(
        entity,
        driver,
        acct,
        bank_enbd,
        gross="1000",
        deductions=[{"kind": "fine", "account": str(acct(SALIK).id), "amount": "1500"}],
    )
    created = client.post("/api/v1/driver-settlements/", payload, format="json")
    assert created.status_code == 201
    posted = client.post(
        f"/api/v1/driver-settlements/{created.data['id']}/post/", {}, format="json"
    )
    assert posted.status_code == 400


def test_negative_net_creates_a_driver_receivable_not_a_bank_entry(entity, driver, bank_enbd, acct):
    """A shortfall is money OWED by the driver — never a bank or cash movement."""
    client = _superuser()
    payload = _settlement_payload(
        entity,
        driver,
        acct,
        bank_enbd,
        gross="1000",
        deductions=[{"kind": "fine", "account": str(acct(SALIK).id), "amount": "1500"}],
        negative=True,
    )
    created = client.post("/api/v1/driver-settlements/", payload, format="json")
    assert created.status_code == 201, created.content
    posted = client.post(
        f"/api/v1/driver-settlements/{created.data['id']}/post/", {}, format="json"
    )
    assert posted.status_code == 200, posted.content
    assert posted.data["net_amount"] == "-500.00"

    je = Settlement.objects.get(id=created.data["id"]).journal_entry
    assert je.total_debit == je.total_credit == D("1500.00")
    # The shortfall lands on the receivable...
    receivable_line = je.lines.get(account=acct(STAFF_ADVANCES))
    assert receivable_line.debit == D("500.00")
    assert receivable_line.driver_id == driver.id  # dimension retained
    # ...and the bank is not touched at all: no receipt is implied by posting.
    assert not je.lines.filter(account=bank_enbd.gl_account).exists()


def test_zero_net_writes_neither_bank_nor_receivable_line(entity, driver, bank_enbd, acct):
    client = _superuser()
    payload = _settlement_payload(
        entity,
        driver,
        acct,
        bank_enbd,
        gross="1000",
        deductions=[{"kind": "fine", "account": str(acct(SALIK).id), "amount": "1000"}],
    )
    created = client.post("/api/v1/driver-settlements/", payload, format="json")
    posted = client.post(
        f"/api/v1/driver-settlements/{created.data['id']}/post/", {}, format="json"
    )
    assert posted.status_code == 200, posted.content
    assert posted.data["net_amount"] == "0.00"

    je = Settlement.objects.get(id=created.data["id"]).journal_entry
    assert je.total_debit == je.total_credit == D("1000.00")
    assert not je.lines.filter(account=bank_enbd.gl_account).exists()
    assert not je.lines.filter(account=acct(STAFF_ADVANCES)).exists()
    assert je.lines.count() == 2  # gross + the single deduction, nothing else


def test_negative_net_rejected_without_a_receivable_account(entity, driver, bank_enbd, acct):
    client = _superuser()
    payload = _settlement_payload(
        entity,
        driver,
        acct,
        bank_enbd,
        gross="1000",
        deductions=[{"kind": "fine", "account": str(acct(SALIK).id), "amount": "1500"}],
        negative=True,
        receivable=None,  # omit it entirely
    )
    res = client.post("/api/v1/driver-settlements/", payload, format="json")
    assert res.status_code == 400
    assert "driver_receivable_account" in res.data


def test_receivable_account_must_belong_to_the_entity(entity, driver, bank_enbd, acct):
    """An account from another entity cannot hold this entity's receivable."""
    other = Entity.objects.create(
        code="OTH", numeric_code="102", legal_name="Other LLC", category=entity.category
    )
    seed_entity_coa(other)
    foreign = Account.objects.get(entity=other, code="102-100-120-003")
    payload = _settlement_payload(
        entity,
        driver,
        acct,
        bank_enbd,
        gross="1000",
        deductions=[{"kind": "fine", "account": str(acct(SALIK).id), "amount": "1500"}],
        negative=True,
        receivable=str(foreign.id),
    )
    res = _superuser().post("/api/v1/driver-settlements/", payload, format="json")
    assert res.status_code == 400
    assert "driver_receivable_account" in res.data


def test_receivable_account_must_be_an_asset(entity, driver, bank_enbd, acct):
    payload = _settlement_payload(
        entity,
        driver,
        acct,
        bank_enbd,
        gross="1000",
        deductions=[{"kind": "fine", "account": str(acct(SALIK).id), "amount": "1500"}],
        negative=True,
        receivable=str(acct(DRIVER_COMMISSION).id),  # an expense account
    )
    res = _superuser().post("/api/v1/driver-settlements/", payload, format="json")
    assert res.status_code == 400
    assert "driver_receivable_account" in res.data


def test_receivable_account_must_be_postable(entity, driver, bank_enbd, acct):
    blocked = acct(STAFF_ADVANCES)
    blocked.is_postable = False
    blocked.save(update_fields=["is_postable"])
    payload = _settlement_payload(
        entity,
        driver,
        acct,
        bank_enbd,
        gross="1000",
        deductions=[{"kind": "fine", "account": str(acct(SALIK).id), "amount": "1500"}],
        negative=True,
    )
    res = _superuser().post("/api/v1/driver-settlements/", payload, format="json")
    assert res.status_code == 400
    assert "driver_receivable_account" in res.data


def test_settlement_duplicate_post_rejected(entity, driver, bank_enbd, acct):
    client = _superuser()
    created = client.post(
        "/api/v1/driver-settlements/",
        _settlement_payload(entity, driver, acct, bank_enbd),
        format="json",
    )
    first = client.post(f"/api/v1/driver-settlements/{created.data['id']}/post/", {}, format="json")
    assert first.status_code == 200
    again = client.post(f"/api/v1/driver-settlements/{created.data['id']}/post/", {}, format="json")
    assert again.status_code == 400


def test_settlement_validates_period_and_gross(entity, driver, bank_enbd, acct):
    client = _superuser()
    bad_period = _settlement_payload(entity, driver, acct, bank_enbd)
    bad_period["period_end"] = date(2026, 5, 1).isoformat()
    res = client.post("/api/v1/driver-settlements/", bad_period, format="json")
    assert res.status_code == 400
    assert "period_end" in res.data

    bad_gross = _settlement_payload(entity, driver, acct, bank_enbd, gross="0")
    res = client.post("/api/v1/driver-settlements/", bad_gross, format="json")
    assert res.status_code == 400
    assert "gross_amount" in res.data


# --- advance recovery -------------------------------------------------------


def test_advance_recovery_updates_balance(entity, driver, bank_enbd, acct):
    client = _superuser()
    advance = _post_advance(client, entity, driver, acct, bank_enbd, amount="1000")

    payload = _settlement_payload(
        entity,
        driver,
        acct,
        bank_enbd,
        gross="5000",
        deductions=[
            {
                "kind": "advance",
                "account": str(acct(STAFF_ADVANCES).id),
                "amount": "400",
                "advance": advance["id"],
            }
        ],
    )
    created = client.post("/api/v1/driver-settlements/", payload, format="json")
    posted = client.post(
        f"/api/v1/driver-settlements/{created.data['id']}/post/", {}, format="json"
    )
    assert posted.status_code == 200, posted.content
    assert posted.data["net_amount"] == "4600.00"

    refreshed = Advance.objects.get(id=advance["id"])
    assert refreshed.recovered_amount == D("400.00")
    assert refreshed.balance == D("600.00")
    # The recovery credits the advance asset back down.
    je = Settlement.objects.get(id=created.data["id"]).journal_entry
    assert je.lines.get(account=acct(STAFF_ADVANCES)).credit == D("400.00")


def test_over_recovery_rejected(entity, driver, bank_enbd, acct):
    client = _superuser()
    advance = _post_advance(client, entity, driver, acct, bank_enbd, amount="1000")
    payload = _settlement_payload(
        entity,
        driver,
        acct,
        bank_enbd,
        gross="5000",
        deductions=[
            {
                "kind": "advance",
                "account": str(acct(STAFF_ADVANCES).id),
                "amount": "1500",  # more than the 1000 outstanding
                "advance": advance["id"],
            }
        ],
    )
    created = client.post("/api/v1/driver-settlements/", payload, format="json")
    posted = client.post(
        f"/api/v1/driver-settlements/{created.data['id']}/post/", {}, format="json"
    )
    assert posted.status_code == 400
    # Nothing was written: the advance is untouched and the settlement stays draft.
    refreshed = Advance.objects.get(id=advance["id"])
    assert refreshed.recovered_amount == D("0.00")
    assert refreshed.balance == D("1000.00")
    assert Settlement.objects.get(id=created.data["id"]).status == DriverDocStatus.DRAFT


def test_split_lines_cannot_jointly_over_recover(entity, driver, bank_enbd, acct):
    """Two lines against one advance are aggregated before the balance check."""
    client = _superuser()
    advance = _post_advance(client, entity, driver, acct, bank_enbd, amount="1000")
    line = {
        "kind": "advance",
        "account": str(acct(STAFF_ADVANCES).id),
        "amount": "600",
        "advance": advance["id"],
    }
    payload = _settlement_payload(
        entity, driver, acct, bank_enbd, gross="5000", deductions=[line, dict(line)]
    )
    created = client.post("/api/v1/driver-settlements/", payload, format="json")
    posted = client.post(
        f"/api/v1/driver-settlements/{created.data['id']}/post/", {}, format="json"
    )
    assert posted.status_code == 400  # 600 + 600 > 1000
    assert Advance.objects.get(id=advance["id"]).balance == D("1000.00")


def test_unposted_advance_cannot_be_recovered(entity, driver, bank_enbd, acct):
    client = _superuser()
    draft = client.post(
        "/api/v1/driver-advances/", _advance_payload(entity, driver, acct, bank_enbd), format="json"
    ).data
    payload = _settlement_payload(
        entity,
        driver,
        acct,
        bank_enbd,
        gross="5000",
        deductions=[
            {
                "kind": "advance",
                "account": str(acct(STAFF_ADVANCES).id),
                "amount": "100",
                "advance": draft["id"],
            }
        ],
    )
    created = client.post("/api/v1/driver-settlements/", payload, format="json")
    posted = client.post(
        f"/api/v1/driver-settlements/{created.data['id']}/post/", {}, format="json"
    )
    assert posted.status_code == 400


# --- isolation & permissions ------------------------------------------------


def test_entity_isolation(entity, driver, bank_enbd, acct):
    owner = _superuser()
    _post_advance(owner, entity, driver, acct, bank_enbd)
    owner.post(
        "/api/v1/driver-settlements/",
        _settlement_payload(entity, driver, acct, bank_enbd),
        format="json",
    )
    # Role granted, no membership → sees nothing.
    outsider = _role_client(entity, role="accountant", member=False)
    assert outsider.get("/api/v1/driver-advances/").data["results"] == []
    assert outsider.get("/api/v1/driver-settlements/").data["results"] == []


def test_role_required(entity, driver, bank_enbd, acct):
    user = User.objects.create_user(email="norole@example.com", password="pw")
    UserEntityMembership.objects.create(user=user, entity=entity)
    client = APIClient()
    client.force_authenticate(user)
    read = client.get("/api/v1/driver-settlements/")
    assert read.status_code == 403
    res = client.post(
        "/api/v1/driver-settlements/",
        _settlement_payload(entity, driver, acct, bank_enbd),
        format="json",
    )
    assert res.status_code == 403


def test_unauthenticated_rejected():
    res = APIClient().get("/api/v1/driver-settlements/")
    assert res.status_code == 401


def test_posted_documents_are_immutable(entity, driver, bank_enbd, acct):
    """No PUT/PATCH/DELETE surface exists for these documents."""
    client = _superuser()
    advance = _post_advance(client, entity, driver, acct, bank_enbd)
    # Hoisted out of the assert: under `python -O` asserts are stripped, so a
    # request made inside one would never fire (CodeQL py/side-effect-in-assert).
    deleted = client.delete(f"/api/v1/driver-advances/{advance['id']}/")
    assert deleted.status_code == 405
    patched = client.patch(
        f"/api/v1/driver-advances/{advance['id']}/", {"amount": "5"}, format="json"
    )
    assert patched.status_code == 405
