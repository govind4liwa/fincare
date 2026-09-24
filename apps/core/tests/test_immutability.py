"""Posted rows cannot be deleted (CLAUDE.md §4.5, AGENTS.md §6).

The general ledger has always guarded itself — ``JournalEntry`` and
``JournalLine`` refuse edits and deletes once posted. The *documents* that post
to it did not: ``BaseModel.delete()`` soft-deleted unconditionally, and 11
viewsets exposed DELETE. A posted sales invoice could be deleted through the
API, leaving its journal entry behind — the GL still carried the revenue and
output VAT while the invoice vanished from every list, report and aging.
"""

import uuid

import pytest

from apps.core.models import PostedRowProtectedError

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# The guard itself (no DB needed — unsaved instances exercise the predicate)
# ---------------------------------------------------------------------------


def test_protected_status_refuses_delete():
    from apps.ar.models import SalesInvoice

    with pytest.raises(PostedRowProtectedError, match="cannot be deleted"):
        SalesInvoice(status="posted")._assert_deletable()


def test_draft_status_is_deletable():
    from apps.ar.models import SalesInvoice

    SalesInvoice(status="draft")._assert_deletable()  # must not raise


def test_gl_link_refuses_delete_even_when_status_is_not_terminal():
    """A document that has posted is protected whatever its status is called.

    ``payroll.Advance`` stays ``open`` after ``pay_advance`` books
    DR Staff Advances / CR Bank, so a status-only check would let a posted
    advance be deleted.
    """
    from apps.payroll.models import Advance

    advance = Advance(status="open", journal_entry_id=uuid.uuid4())
    with pytest.raises(PostedRowProtectedError, match="posted to the general ledger"):
        advance._assert_deletable()


def test_hard_delete_is_guarded_too():
    """The escape hatch exists for drafts and test data, not for posted rows."""
    from apps.vouchers.models import Voucher

    with pytest.raises(PostedRowProtectedError):
        Voucher(status="posted").hard_delete()


# ---------------------------------------------------------------------------
# Structural: every document that can enter the record declares its protection
# ---------------------------------------------------------------------------

# Statuses that mean "this row is part of the accounting record".
RECORD_STATUSES = {
    "posted",
    "reversed",
    "cancelled",
    "paid",
    "partially_paid",
    "filed",
    "settled",
    "approved",
    "completed",
    "reconciled",
    "closed",
    "locked",
    "superseded",
    "finalised",
    "submitted",
    "invoiced",
    "recovering",
    "cleared",
}

# Models whose status looks terminal but which are operational logs, not
# accounting documents — deleting one cannot put the books out of balance.
NOT_ACCOUNTING_DOCUMENTS = {
    "integrations.ImportBatch",  # record of an import run
    "reports.ReportRun",  # record of a report render
}


def test_every_document_that_can_enter_the_record_declares_protection():
    """Guards the failure mode this test module exists for.

    A new document model ships with a `posted` status, nobody sets
    DELETE_PROTECTED_STATUSES, and it is silently deletable after posting.
    """
    from django.apps import apps as django_apps

    unprotected = []
    for model in django_apps.get_models():
        if not model._meta.managed or model._meta.proxy:
            continue
        label = f"{model._meta.app_label}.{model.__name__}"
        if label in NOT_ACCOUNTING_DOCUMENTS:
            continue
        field = next(
            (f for f in model._meta.get_fields() if getattr(f, "attname", None) == "status"), None
        )
        if field is None or not getattr(field, "choices", None):
            continue
        if not {str(c[0]) for c in field.choices} & RECORD_STATUSES:
            continue
        if not getattr(model, "DELETE_PROTECTED_STATUSES", ()):
            unprotected.append(label)

    assert sorted(unprotected) == [], (
        "these models can reach a status that puts them in the accounting record "
        "but declare no DELETE_PROTECTED_STATUSES — add it, or list them in "
        f"NOT_ACCOUNTING_DOCUMENTS with a reason: {sorted(unprotected)}"
    )


def test_declared_statuses_are_real_choices():
    """A typo in DELETE_PROTECTED_STATUSES would silently protect nothing."""
    from django.apps import apps as django_apps

    bad = []
    for model in django_apps.get_models():
        declared = getattr(model, "DELETE_PROTECTED_STATUSES", ())
        if not declared:
            continue
        field = next(
            (f for f in model._meta.get_fields() if getattr(f, "attname", None) == "status"), None
        )
        if field is None or not getattr(field, "choices", None):
            bad.append(f"{model.__name__}: declares statuses but has no status field")
            continue
        valid = {str(c[0]) for c in field.choices}
        unknown = sorted(set(declared) - valid)
        if unknown:
            bad.append(f"{model.__name__}: {unknown} not in {sorted(valid)}")
    assert bad == [], bad
