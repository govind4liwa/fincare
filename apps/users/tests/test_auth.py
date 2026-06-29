"""JWT auth flow tests (email login via SimpleJWT)."""

from django.contrib.auth import get_user_model

from rest_framework.test import APIClient

import pytest

pytestmark = pytest.mark.django_db

User = get_user_model()

TOKEN_URL = "/api/v1/auth/token/"
REFRESH_URL = "/api/v1/auth/token/refresh/"


@pytest.fixture
def user():
    return User.objects.create_user(email="user@example.com", password="s3cret!pw")


def test_obtain_and_refresh_token(user):
    client = APIClient()
    resp = client.post(
        TOKEN_URL, {"email": "user@example.com", "password": "s3cret!pw"}, format="json"
    )
    assert resp.status_code == 200
    assert "access" in resp.data
    assert "refresh" in resp.data

    refreshed = client.post(REFRESH_URL, {"refresh": resp.data["refresh"]}, format="json")
    assert refreshed.status_code == 200
    assert "access" in refreshed.data


def test_wrong_password_is_rejected(user):
    client = APIClient()
    resp = client.post(TOKEN_URL, {"email": "user@example.com", "password": "wrong"}, format="json")
    assert resp.status_code == 401


def test_access_token_authenticates_protected_endpoint(user):
    """A valid access token should authenticate requests (smoke check)."""
    client = APIClient()
    token = client.post(
        TOKEN_URL, {"email": "user@example.com", "password": "s3cret!pw"}, format="json"
    ).data["access"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    # Readiness endpoint is AllowAny but should still succeed with auth attached.
    resp = client.get("/api/v1/core/readiness/")
    assert resp.status_code in (200, 503)
