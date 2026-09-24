# ADR-0011 — Deletion Protection for Posted Accounting Documents

**Status:** Accepted
**Date:** 2026-09-24
**Author:** Govind
**Supersedes:** —
**Superseded by:** —
**Related:** ADR-0007 (posting engine), CLAUDE.md §4.5, AGENTS.md §6

---

## Context

CLAUDE.md §4.5 and AGENTS.md §6 both state that posted accounting transactions
are never deleted — corrections go through a reversal or a credit/debit note.
The general ledger enforced this for itself: `JournalEntry` and `JournalLine`
override `save()` and `delete()` and refuse once the entry is posted, reversed
or cancelled.

The **documents that post to the ledger** did not. `BaseModel.delete()`
soft-deleted unconditionally, with no status check, and 11 document viewsets
exposed `DELETE` through the default `ModelViewSet` method set.

Confirmed behaviourally before fixing: a sales invoice was created, posted
(producing a balanced journal entry of AED 1,050.00), and then deleted through
`DELETE /api/v1/invoices/{id}/`, which returned **204**. The invoice was
soft-deleted (`is_deleted=True`) while its journal entry remained posted. The
GL still carried the revenue and output VAT; the invoice disappeared from every
list, report and aging, because the default manager excludes soft-deleted rows.
The AR subledger and the GL silently disagreed, and the audit trail from ledger
entry back to source document was broken.

Editing was already guarded, but ad hoc — AR's serializer raises "Only draft
invoices can be edited" in `update()`. That pattern is per-serializer and easy
to omit; deletion had no equivalent anywhere.

---

## Decision

Guard deletion in `apps.core.BaseModel`, so every path is covered — REST API,
Django admin, management commands, shell, and service code — rather than only
the API surface.

### 1. Two independent tests, because neither alone is sufficient

```python
def _assert_deletable(self):
    if getattr(self, "journal_entry_id", None) is not None:
        raise PostedRowProtectedError(...)      # it has hit the ledger
    if self.status in self.DELETE_PROTECTED_STATUSES:
        raise PostedRowProtectedError(...)      # it is part of the record
```

* **A linked `journal_entry`** means the document has posted, whatever its
  status happens to be called. `payroll.Advance` stays `open` after
  `pay_advance` books DR Staff Advances / CR Bank, so a status check alone
  would let a posted advance be deleted.
* **`DELETE_PROTECTED_STATUSES`**, declared per model, covers rows that are part
  of the record without a journal entry of their own: a filed tax return, a
  completed bank reconciliation, an approved loan schedule, a closed period, a
  reconciled bank statement.

Both `delete()` (soft) and `hard_delete()` are guarded. `hard_delete` exists to
clean up drafts and test data, and must not become a way around this.

### 2. Drafts stay deletable

The guard is deliberately narrow. An unposted draft is still disposable, which
keeps data entry forgiving — only entering the accounting record is one-way.

### 3. `PostedRowProtectedError` subclasses `ValueError`

Existing `except ValueError` handlers around model writes keep working, matching
the ledger's own guards, which already raise `ValueError`.

### 4. The API answers 409, not 500

A new DRF `EXCEPTION_HANDLER` (`apps.core.exceptions`) maps the error to **409
Conflict** — the request is well formed, it conflicts with the resource's state.
The response carries our own curated message (model, id, and what to do
instead), never raw exception internals.

---

## Alternatives Considered

| Option | Rejected because |
|---|---|
| Remove `delete` from each viewset's `http_method_names` | Guards only the API. Admin, shell and service code could still delete, and it would also block deleting drafts, which is legitimate. |
| Per-model `delete()` overrides, as `JournalEntry` does | Correct but repeated 28 times; the next model to ship would simply omit it — exactly how this gap arose. |
| Database triggers | Strongest, but splits the rule across two languages and is invisible to the ORM and to tests. Reserved for if the Python guard proves insufficient. |
| Block edits the same way | Editing is already refused per serializer, and several services legitimately update posted documents (an allocation moves a posted invoice to `paid`). A blanket `save()` guard would need `JournalEntry`'s `_system_update` escape hatch on every model — invasive, and a separate concern from deletion. |

---

## Consequences

**Easier:** the rule holds on every path, not just REST; new posting apps
inherit it by declaring one tuple; a structural test fails the build if a model
can reach a record status without declaring protection.

**Harder:** `DELETE_PROTECTED_STATUSES` must be kept honest. Two tests defend
it — one asserting every model that can reach a record status declares it, one
asserting the declared statuses are real choices of that model's `status` field,
so a typo cannot silently protect nothing.

---

## Risks

- **Over-reach** — blocking deletion of something that should be disposable.
  Mitigated by scoping to a declared status list plus the ledger link, and by a
  test that a draft is still deletable.
- **Queryset deletes bypass it.** `Model.objects.filter(...).delete()` does not
  call `Model.delete()`. No application code does this, and the API path uses
  the instance method, but it remains the way around the guard. A database
  trigger is the escape hatch if that changes.
- **Operational logs** (`integrations.ImportBatch`, `reports.ReportRun`) are
  deliberately unprotected — deleting one cannot unbalance the books. They are
  listed explicitly in the test rather than left to inference.

---

## Migration Notes

No schema change and no migration: `DELETE_PROTECTED_STATUSES` is a Python class
attribute. Behaviour changes immediately on deploy — a `DELETE` against a posted
document that previously returned 204 now returns 409. No frontend currently
offers such a control, so no UI change is required.
