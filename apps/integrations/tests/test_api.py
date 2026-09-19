"""API tests for integrations: import profiles CRUD/scoping and the two
multipart upload actions (bank statement, platform earnings)."""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings

from rest_framework.test import APIClient

import pytest

from apps.banking.models import StatementLine
from apps.integrations.models import ImportBatch, ImportKind, ImportProfile
from apps.platforms.models import EarningImport
from apps.tenants.models import Entity, UserEntityMembership

from .test_integrations import BANK_CSV, _platform_xlsx

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


def _csv_upload(content=BANK_CSV, name="enbd.csv"):
    return SimpleUploadedFile(name, content.encode(), content_type="text/csv")


def test_member_without_role_can_read_but_not_upload(entity, bank_account, bank_profile):
    client = _client(entity, role=None)
    batches = client.get("/api/v1/import-batches/")
    profiles = client.get("/api/v1/import-profiles/")
    assert batches.status_code == 200
    assert profiles.status_code == 200

    res = client.post(
        "/api/v1/import-batches/bank-statement/",
        {
            "file": _csv_upload(),
            "bank_account": str(bank_account.id),
            "profile": str(bank_profile.id),
        },
        format="multipart",
    )
    assert res.status_code == 403


def test_create_profile_requires_kind_mapping(entity):
    client = _client(entity, "accountant")
    res = client.post(
        "/api/v1/import-profiles/",
        {
            "entity": str(entity.id),
            "kind": "bank_statement",
            "name": "Bad",
            "source_key": "BAD",
            "column_map": {"description": "Narrative"},  # txn_date missing
        },
        format="json",
    )
    assert res.status_code == 400
    assert "txn_date" in str(res.data["column_map"])

    res = client.post(
        "/api/v1/import-profiles/",
        {
            "entity": str(entity.id),
            "kind": "bank_statement",
            "name": "Bad2",
            "source_key": "BAD2",
            "column_map": {"txn_date": "Date", "txndate": "Date"},  # unknown key
        },
        format="json",
    )
    assert res.status_code == 400
    assert "txndate" in str(res.data["column_map"])


def test_profiles_scoped_to_entities_plus_global(entity, bank_profile):
    other = Entity.objects.create(
        code="OTH",
        numeric_code="102",
        legal_name="Other Transport LLC",
        category=entity.category,
        base_currency=entity.base_currency,
    )
    ImportProfile.objects.create(
        entity=other,
        kind=ImportKind.BANK_STATEMENT,
        name="Other bank",
        source_key="OTHER",
        column_map={"txn_date": "Date"},
    )
    ImportProfile.objects.create(
        entity=None,
        kind=ImportKind.BANK_STATEMENT,
        name="Group-wide",
        source_key="GLOBAL",
        column_map={"txn_date": "Date"},
    )
    client = _client(entity, "accountant")
    res = client.get("/api/v1/import-profiles/")
    assert res.status_code == 200
    keys = {p["source_key"] for p in res.data["results"]}
    assert keys == {"ENBD", "GLOBAL"}


def test_upload_bank_statement_csv_and_idempotent_reupload(entity, bank_account, bank_profile):
    client = _client(entity, "accountant")
    payload = {
        "file": _csv_upload(),
        "bank_account": str(bank_account.id),
        "profile": str(bank_profile.id),
        "statement_no": "JUN-01",
    }
    res = client.post("/api/v1/import-batches/bank-statement/", payload, format="multipart")
    assert res.status_code == 201
    assert res.data["created_count"] == 2
    assert res.data["skipped_count"] == 0
    assert res.data["status"] == "done"
    assert res.data["bank_statement"] is not None
    assert StatementLine.objects.filter(statement__bank_account=bank_account).count() == 2

    payload["file"] = _csv_upload()
    again = client.post("/api/v1/import-batches/bank-statement/", payload, format="multipart")
    assert again.status_code == 201
    assert again.data["created_count"] == 0
    assert again.data["skipped_count"] == 2
    assert StatementLine.objects.filter(statement__bank_account=bank_account).count() == 2


def test_upload_with_wrong_kind_profile_rejected(entity, bank_account, platform_profile):
    client = _client(entity, "accountant")
    res = client.post(
        "/api/v1/import-batches/bank-statement/",
        {
            "file": _csv_upload(),
            "bank_account": str(bank_account.id),
            "profile": str(platform_profile.id),
        },
        format="multipart",
    )
    assert res.status_code == 400
    assert "profile" in res.data


def test_failed_import_records_error_batch(entity, bank_account, bank_profile):
    client = _client(entity, "accountant")
    bad = "Narrative,Ref,Debit,Credit\nSalik,RF1,100.00,\n"  # mapped "Date" column missing
    res = client.post(
        "/api/v1/import-batches/bank-statement/",
        {
            "file": _csv_upload(bad, name="bad.csv"),
            "bank_account": str(bank_account.id),
            "profile": str(bank_profile.id),
        },
        format="multipart",
    )
    assert res.status_code == 400
    assert res.data["batch"]
    batch = ImportBatch.objects.get(pk=res.data["batch"])
    assert batch.status == ImportBatch.Status.ERROR
    assert "Date" in batch.message
    assert StatementLine.objects.count() == 0

    listed = client.get("/api/v1/import-batches/?status=error")
    assert listed.status_code == 200
    assert listed.data["results"][0]["message"] == batch.message


def test_upload_platform_earnings_xlsx(entity, platform, platform_profile):
    client = _client(entity, "accountant")
    content = _platform_xlsx(
        [
            ["2026-06-01", "T1", "D001", 100.00, 20.00, 80.00],
            ["2026-06-01", "T2", "D002", 150.00, 30.00, 120.00],
        ]
    )
    res = client.post(
        "/api/v1/import-batches/platform-earnings/",
        {
            "file": SimpleUploadedFile(
                "uber.xlsx",
                content,
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
            "platform": str(platform.id),
            "profile": str(platform_profile.id),
        },
        format="multipart",
    )
    assert res.status_code == 201
    assert res.data["created_count"] == 2
    assert EarningImport.objects.filter(platform=platform).count() == 2


def test_unsupported_extension_rejected(entity, bank_account, bank_profile):
    client = _client(entity, "accountant")
    res = client.post(
        "/api/v1/import-batches/bank-statement/",
        {
            "file": SimpleUploadedFile("scan.pdf", b"%PDF-", content_type="application/pdf"),
            "bank_account": str(bank_account.id),
            "profile": str(bank_profile.id),
        },
        format="multipart",
    )
    assert res.status_code == 400
    assert "file" in res.data


@override_settings(INTEGRATIONS_MAX_UPLOAD_MB=0)
def test_oversize_file_rejected(entity, bank_account, bank_profile):
    client = _client(entity, "accountant")
    res = client.post(
        "/api/v1/import-batches/bank-statement/",
        {
            "file": _csv_upload(),
            "bank_account": str(bank_account.id),
            "profile": str(bank_profile.id),
        },
        format="multipart",
    )
    assert res.status_code == 400
    assert "file" in res.data


def test_cross_entity_bank_account_blocked(entity, bank_account, bank_profile):
    other = Entity.objects.create(
        code="OTH",
        numeric_code="102",
        legal_name="Other Transport LLC",
        category=entity.category,
        base_currency=entity.base_currency,
    )
    client = _client(other, "accountant")  # member of the other entity only
    res = client.post(
        "/api/v1/import-batches/bank-statement/",
        {
            "file": _csv_upload(),
            "bank_account": str(bank_account.id),
            "profile": str(bank_profile.id),
        },
        format="multipart",
    )
    assert res.status_code == 400
    assert "bank_account" in res.data
