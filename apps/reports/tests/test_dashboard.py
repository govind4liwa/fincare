"""API test for the dashboard KPI endpoint."""

from django.contrib.auth import get_user_model

from rest_framework.test import APIClient

import pytest

pytestmark = pytest.mark.django_db
User = get_user_model()

BANK = "100-110-010"
REVENUE = "400-410-001"
EXPENSE = "500-530-001"


def test_dashboard_kpis(entity, post_entry):
    # Revenue 1000 (DR bank / CR revenue) and an expense 300 (DR expense / CR bank).
    post_entry(entity, [(BANK, 1000, 0), (REVENUE, 0, 1000)])
    post_entry(entity, [(EXPENSE, 300, 0), (BANK, 0, 300)])

    su = User.objects.create_superuser(email="root@example.com", password="pw")
    client = APIClient()
    client.force_authenticate(su)
    res = client.get(f"/api/v1/reports/dashboard/?entity={entity.id}")

    assert res.status_code == 200
    assert res.data["revenue"] == "1000.00"
    assert res.data["expenses"] == "300.00"
    assert res.data["cash_bank"] == "700.00"  # 1000 in − 300 out
    assert res.data["period"] is not None


def test_dashboard_requires_auth():
    assert APIClient().get("/api/v1/reports/dashboard/").status_code == 401
