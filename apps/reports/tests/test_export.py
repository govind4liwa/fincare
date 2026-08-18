"""Report export endpoint — JSON, xlsx and pdf (via ?export=, not ?format=)."""

from django.contrib.auth import get_user_model

from rest_framework.test import APIClient

import pytest

pytestmark = pytest.mark.django_db
User = get_user_model()

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
BANK = "100-110-010"
REVENUE = "400-410-001"


def _client():
    client = APIClient()
    client.force_authenticate(
        User.objects.create_superuser(email="root@example.com", password="pw")
    )
    return client


def test_report_json(entity, period, post_entry):
    post_entry(entity, [(BANK, 1000, 0), (REVENUE, 0, 1000)])
    res = _client().get(
        f"/api/v1/reports/TB/?entity_id={entity.id}&period_id={period.id}&export=json"
    )
    assert res.status_code == 200
    assert res.data["report"]["code"] == "TB"


def test_report_xlsx_export(entity, period, post_entry):
    post_entry(entity, [(BANK, 1000, 0), (REVENUE, 0, 1000)])
    res = _client().get(
        f"/api/v1/reports/TB/?entity_id={entity.id}&period_id={period.id}&export=xlsx"
    )
    assert res.status_code == 200
    assert res["Content-Type"] == XLSX_MIME
    assert res.content[:2] == b"PK"  # xlsx is a zip archive


def test_report_pdf_export(entity, period, post_entry):
    post_entry(entity, [(BANK, 1000, 0), (REVENUE, 0, 1000)])
    res = _client().get(
        f"/api/v1/reports/TB/?entity_id={entity.id}&period_id={period.id}&export=pdf"
    )
    assert res.status_code == 200
    assert res["Content-Type"] == "application/pdf"
    assert res.content[:5] == b"%PDF-"
    assert res["Content-Disposition"] == 'attachment; filename="TB.pdf"'
