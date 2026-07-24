"""Tests for core BaseModel soft delete and Currency constraints."""

import uuid

from django.db import IntegrityError, transaction

import pytest

from apps.core.models import Currency

pytestmark = pytest.mark.django_db


def _make_currency(code="AED", is_base=False):
    return Currency.objects.create(code=code, name=f"{code} name", symbol=code, is_base=is_base)


class TestSoftDelete:
    def test_delete_flags_row_and_hides_from_default_manager(self):
        cur = _make_currency("USD")
        cur.delete()

        assert cur.is_deleted is True
        assert cur.deleted_at is not None
        # Default manager hides it...
        assert not Currency.objects.filter(pk=cur.pk).exists()
        # ...but it still physically exists.
        assert Currency.all_objects.filter(pk=cur.pk).exists()

    def test_queryset_delete_is_soft(self):
        _make_currency("EUR")
        _make_currency("GBP")
        Currency.objects.all().delete()

        assert Currency.objects.count() == 0
        assert Currency.all_objects.count() == 2

    def test_hard_delete_removes_row(self):
        cur = _make_currency("INR")
        cur.hard_delete()
        assert not Currency.all_objects.filter(pk=cur.pk).exists()

    def test_pk_is_uuid(self):
        cur = _make_currency("AED")
        assert isinstance(cur.pk, uuid.UUID)


class TestSingleBaseCurrency:
    def test_only_one_base_currency_allowed(self):
        _make_currency("AED", is_base=True)
        with pytest.raises(IntegrityError), transaction.atomic():
            _make_currency("USD", is_base=True)
