"""Tests for the custom User model and manager."""

import uuid

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction

import pytest

pytestmark = pytest.mark.django_db

User = get_user_model()


def test_create_user_sets_email_and_password():
    user = User.objects.create_user(email="Jane@Example.com", password="s3cret!pw")
    assert user.email == "Jane@example.com"  # domain normalised
    assert user.check_password("s3cret!pw")
    assert user.is_active
    assert not user.is_staff
    assert not user.is_superuser


def test_create_superuser_flags():
    admin = User.objects.create_superuser(email="admin@example.com", password="s3cret!pw")
    assert admin.is_staff
    assert admin.is_superuser


def test_email_is_required():
    with pytest.raises(ValueError):
        User.objects.create_user(email="", password="x")


def test_pk_is_uuid_and_str_is_email():
    user = User.objects.create_user(email="u@example.com", password="x")
    assert isinstance(user.pk, uuid.UUID)
    assert str(user) == "u@example.com"


def test_email_unique():
    User.objects.create_user(email="dup@example.com", password="x")
    with pytest.raises(IntegrityError), transaction.atomic():
        User.objects.create_user(email="dup@example.com", password="y")
