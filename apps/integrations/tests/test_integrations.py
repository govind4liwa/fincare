"""Importer tests: bank statement (CSV) + platform earnings (XLSX), idempotent."""

from decimal import Decimal
from io import BytesIO

import pytest

from apps.banking.models import StatementLine
from apps.integrations.services.bank import import_bank_statement
from apps.integrations.services.parsers import IntegrationError
from apps.integrations.services.platform import import_platform_earnings
from apps.platforms.models import EarningImport

pytestmark = pytest.mark.django_db

BANK_CSV = (
    "Date,Narrative,Ref,Debit,Credit,Balance\n"
    "01/06/2026,Salik top-up,RF1,100.00,,5000.00\n"
    "02/06/2026,Customer deposit,RF2,,2500.00,7500.00\n"
)


def _platform_xlsx(rows):
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["Date", "Trip", "Driver", "Gross", "Commission", "Net"])
    for r in rows:
        ws.append(r)
    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def test_import_bank_statement_csv(bank_account, bank_profile):
    batch = import_bank_statement(
        bank_account=bank_account, profile=bank_profile, content=BANK_CSV, filename="enbd.csv"
    )
    assert batch.created_count == 2
    assert batch.skipped_count == 0
    stmt = batch.bank_statement
    assert stmt is not None
    assert stmt.period_start.isoformat() == "2026-06-01"
    assert stmt.period_end.isoformat() == "2026-06-02"

    lines = list(StatementLine.objects.filter(statement=stmt).order_by("line_no"))
    assert len(lines) == 2
    assert lines[0].txn_date.isoformat() == "2026-06-01"
    assert lines[0].withdrawal == Decimal("100.00")
    assert lines[0].deposit == Decimal("0.00")
    assert lines[1].deposit == Decimal("2500.00")
    assert lines[1].running_balance == Decimal("7500.00")


def test_bank_reimport_is_idempotent(bank_account, bank_profile):
    import_bank_statement(
        bank_account=bank_account, profile=bank_profile, content=BANK_CSV, filename="enbd.csv"
    )
    again = import_bank_statement(
        bank_account=bank_account, profile=bank_profile, content=BANK_CSV, filename="enbd.csv"
    )
    assert again.created_count == 0
    assert again.skipped_count == 2
    assert again.bank_statement is None  # empty header removed
    assert StatementLine.objects.filter(statement__bank_account=bank_account).count() == 2


def test_missing_required_column_raises(bank_account, bank_profile):
    # File lacks the mapped "Date" column.
    bad = "Narrative,Ref,Debit,Credit\nSalik,RF1,100.00,\n"
    with pytest.raises(IntegrationError, match="Date"):
        import_bank_statement(
            bank_account=bank_account, profile=bank_profile, content=bad, filename="bad.csv"
        )


def test_import_platform_earnings_xlsx(platform, platform_profile):
    content = _platform_xlsx(
        [
            ["2026-06-01", "T1", "D001", 100.00, 20.00, 80.00],
            ["2026-06-01", "T2", "D002", 150.00, 30.00, 120.00],
        ]
    )
    batch = import_platform_earnings(
        platform=platform, profile=platform_profile, content=content, filename="uber.xlsx"
    )
    assert batch.created_count == 2
    rows = {r.trip_ref: r for r in EarningImport.objects.filter(platform=platform)}
    assert rows["T1"].gross == Decimal("100.00")
    assert rows["T1"].commission == Decimal("20.00")
    assert rows["T1"].net == Decimal("80.00")
    assert rows["T2"].net == Decimal("120.00")


def test_platform_net_defaults_to_gross_minus_commission(platform, platform_profile):
    content = _platform_xlsx([["2026-06-02", "T9", "D001", 200.00, 40.00, None]])
    import_platform_earnings(
        platform=platform, profile=platform_profile, content=content, filename="uber.xlsx"
    )
    row = EarningImport.objects.get(platform=platform, trip_ref="T9")
    assert row.net == Decimal("160.00")  # 200 - 40


def test_platform_reimport_is_idempotent(platform, platform_profile):
    content = _platform_xlsx([["2026-06-01", "T1", "D001", 100.00, 20.00, 80.00]])
    import_platform_earnings(
        platform=platform, profile=platform_profile, content=content, filename="uber.xlsx"
    )
    again = import_platform_earnings(
        platform=platform, profile=platform_profile, content=content, filename="uber.xlsx"
    )
    assert again.created_count == 0
    assert again.skipped_count == 1
    assert EarningImport.objects.filter(platform=platform, trip_ref="T1").count() == 1
