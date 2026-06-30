"""Import a bank statement file into ``banking.StatementLine`` rows.

The ``ImportProfile.column_map`` maps canonical fields (txn_date, description,
reference, deposit, withdrawal, running_balance) to the bank's column headers.
Re-importing the same file (or an overlapping one) is idempotent: a line already
present for the bank account (same date + reference + amounts) is skipped.
"""

from django.db import transaction
from django.utils import timezone

from apps.banking.models import BankStatement, StatementLine
from apps.integrations.models import ImportBatch, ImportKind
from apps.integrations.services.parsers import (
    IntegrationError,
    file_hash,
    read_rows,
    to_date,
    to_decimal,
)

REQUIRED = ("txn_date",)


def _validate_map(column_map, headers):
    for field, header in column_map.items():
        if header and header not in headers:
            raise IntegrationError(
                f"Mapped column {header!r} (for {field!r}) not found in file headers {headers}."
            )
    for field in REQUIRED:
        if not column_map.get(field):
            raise IntegrationError(f"Bank profile must map the {field!r} field.")


def _cell(row, column_map, field):
    header = column_map.get(field)
    return row.get(header) if header else None


def _line_key(bank_account_id, txn_date, reference, deposit, withdrawal):
    return (bank_account_id, txn_date, reference, str(deposit), str(withdrawal))


@transaction.atomic
def import_bank_statement(*, bank_account, profile, content, filename, statement_no="", user=None):
    headers, rows = read_rows(content, filename, skip_rows=profile.skip_rows, sheet=profile.sheet)
    column_map = profile.column_map
    _validate_map(column_map, headers)
    entity = bank_account.entity

    statement = BankStatement.objects.create(
        entity=entity,
        bank_account=bank_account,
        statement_no=statement_no,
        statement_date=timezone.now().date(),
    )

    seen = set()
    created = skipped = 0
    dates = []
    line_no = 0
    for row in rows:
        txn_date = to_date(_cell(row, column_map, "txn_date"), profile.date_format)
        reference = str(_cell(row, column_map, "reference") or "").strip()
        deposit = to_decimal(_cell(row, column_map, "deposit"))
        withdrawal = to_decimal(_cell(row, column_map, "withdrawal"))
        description = str(_cell(row, column_map, "description") or "").strip()
        rb_raw = _cell(row, column_map, "running_balance")
        running_balance = to_decimal(rb_raw) if rb_raw not in (None, "") else None

        key = _line_key(bank_account.id, txn_date, reference, deposit, withdrawal)
        exists = StatementLine.objects.filter(
            statement__bank_account=bank_account,
            txn_date=txn_date,
            reference=reference,
            deposit=deposit,
            withdrawal=withdrawal,
        ).exists()
        if key in seen or exists:
            skipped += 1
            continue

        line_no += 1
        StatementLine.objects.create(
            statement=statement,
            line_no=line_no,
            txn_date=txn_date,
            description=description,
            reference=reference,
            deposit=deposit,
            withdrawal=withdrawal,
            running_balance=running_balance,
        )
        seen.add(key)
        dates.append(txn_date)
        created += 1

    if created:
        statement.period_start = min(dates)
        statement.period_end = max(dates)
        statement.statement_date = max(dates)
        statement.save(update_fields=["period_start", "period_end", "statement_date", "updated_at"])
    else:
        statement.delete()  # idempotent re-import leaves no empty header
        statement = None

    return ImportBatch.objects.create(
        entity=entity,
        profile=profile,
        kind=ImportKind.BANK_STATEMENT,
        filename=filename,
        file_hash=file_hash(content),
        bank_account=bank_account,
        bank_statement=statement,
        row_count=len(rows),
        created_count=created,
        skipped_count=skipped,
        status=ImportBatch.Status.DONE,
        imported_at=timezone.now(),
        imported_by=user,
        message=f"{created} created, {skipped} duplicates skipped",
    )


# Re-export so importers share one error type.
__all__ = ["IntegrationError", "ZERO", "import_bank_statement"]
