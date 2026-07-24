"""Tests for gap-safe, concurrency-safe number allocation."""

import uuid
from concurrent.futures import ThreadPoolExecutor

from django.db import connection

import pytest

from apps.core.services import sequences

pytestmark = pytest.mark.django_db


def test_allocate_is_contiguous_and_formats():
    entity_id = uuid.uuid4()
    results = [
        sequences.allocate(entity_id=entity_id, code="SALES_INV", prefix="INV-", padding=6)
        for _ in range(5)
    ]
    assert [r.value for r in results] == [1, 2, 3, 4, 5]
    assert results[0].formatted == "INV-000001"
    assert results[4].formatted == "INV-000005"


def test_scopes_are_independent():
    e1, e2 = uuid.uuid4(), uuid.uuid4()
    assert sequences.allocate(entity_id=e1, code="RV").value == 1
    assert sequences.allocate(entity_id=e2, code="RV").value == 1  # different entity
    assert sequences.allocate(entity_id=e1, code="PV").value == 1  # different code
    assert sequences.allocate(entity_id=e1, code="RV").value == 2  # continues e1/RV


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
def test_allocate_unique_under_concurrency():
    """No two concurrent callers receive the same number (row lock holds)."""
    entity_id = uuid.uuid4()
    n = 20
    # Pre-create the counter so threads don't race on get_or_create.
    sequences.ensure_sequence(entity_id=entity_id, code="JE")

    def worker():
        try:
            return sequences.allocate(entity_id=entity_id, code="JE").value
        finally:
            connection.close()  # each thread uses its own connection

    with ThreadPoolExecutor(max_workers=n) as pool:
        values = list(pool.map(lambda _: worker(), range(n)))

    assert sorted(values) == list(range(1, n + 1))  # unique + contiguous
    assert len(set(values)) == n
