"""Tests for the core health endpoints."""

from rest_framework import status
from rest_framework.test import APIClient

import pytest

pytestmark = pytest.mark.django_db


@pytest.fixture
def client() -> APIClient:
    return APIClient()


def test_liveness_returns_200_and_payload(client: APIClient) -> None:
    response = client.get("/health/")
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "fincare"
    assert "django" in body
    assert "version" in body


def test_readiness_returns_200_when_db_and_cache_ok(client: APIClient) -> None:
    response = client.get("/health/ready/")
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["status"] == "ok"
    assert body["checks"]["database"] == "ok"
    assert body["checks"]["cache"] == "ok"


def test_liveness_endpoint_does_not_require_auth(client: APIClient) -> None:
    # No Authorization header set
    response = client.get("/health/")
    assert response.status_code == status.HTTP_200_OK


def test_liveness_via_api_v1_route(client: APIClient) -> None:
    response = client.get("/api/v1/core/liveness/")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == "ok"


def test_readiness_via_api_v1_route(client: APIClient) -> None:
    response = client.get("/api/v1/core/readiness/")
    assert response.status_code == status.HTTP_200_OK


def test_openapi_schema_endpoint_available(client: APIClient) -> None:
    response = client.get("/api/schema/")
    assert response.status_code == status.HTTP_200_OK
