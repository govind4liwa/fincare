"""Import a platform earnings file into ``platforms.EarningImport`` rows.

The ``ImportProfile.column_map`` maps canonical fields (earning_date, trip_ref,
driver_ref, gross, commission, net) to the platform export's headers. Re-importing
is idempotent: a row already staged for the platform (same trip_ref, or same
date+amounts when no trip_ref) is skipped.
"""

from django.db import transaction
from django.utils import timezone

from apps.integrations.models import ImportBatch, ImportKind
from apps.integrations.services.parsers import (
    IntegrationError,
    file_hash,
    read_rows,
    to_date,
    to_decimal,
)
from apps.platforms.models import EarningImport

REQUIRED = ("earning_date", "gross")


def _validate_map(column_map, headers):
    for field, header in column_map.items():
        if header and header not in headers:
            raise IntegrationError(
                f"Mapped column {header!r} (for {field!r}) not found in file headers {headers}."
            )
    for field in REQUIRED:
        if not column_map.get(field):
            raise IntegrationError(f"Platform profile must map the {field!r} field.")


def _cell(row, column_map, field):
    header = column_map.get(field)
    return row.get(header) if header else None


def _exists(platform, trip_ref, earning_date, gross, net):
    qs = EarningImport.objects.filter(platform=platform)
    if trip_ref:
        return qs.filter(trip_ref=trip_ref).exists()
    return qs.filter(earning_date=earning_date, gross=gross, net=net).exists()


@transaction.atomic
def import_platform_earnings(*, platform, profile, content, filename, user=None):
    headers, rows = read_rows(content, filename, skip_rows=profile.skip_rows, sheet=profile.sheet)
    column_map = profile.column_map
    _validate_map(column_map, headers)
    entity = platform.entity

    seen = set()
    created = skipped = 0
    for row in rows:
        earning_date = to_date(_cell(row, column_map, "earning_date"), profile.date_format)
        trip_ref = str(_cell(row, column_map, "trip_ref") or "").strip()
        driver_ref = str(_cell(row, column_map, "driver_ref") or "").strip()
        gross = to_decimal(_cell(row, column_map, "gross"))
        commission = to_decimal(_cell(row, column_map, "commission"))
        net_raw = _cell(row, column_map, "net")
        net = to_decimal(net_raw) if net_raw not in (None, "") else gross - commission

        key = (trip_ref, str(earning_date), str(gross), str(net))
        if key in seen or _exists(platform, trip_ref, earning_date, gross, net):
            skipped += 1
            continue

        EarningImport.objects.create(
            entity=entity,
            platform=platform,
            trip_ref=trip_ref,
            driver_ref=driver_ref,
            earning_date=earning_date,
            gross=gross,
            commission=commission,
            net=net,
            matched=False,
        )
        seen.add(key)
        created += 1

    return ImportBatch.objects.create(
        entity=entity,
        profile=profile,
        kind=ImportKind.PLATFORM_EARNING,
        filename=filename,
        file_hash=file_hash(content),
        platform=platform,
        row_count=len(rows),
        created_count=created,
        skipped_count=skipped,
        status=ImportBatch.Status.DONE,
        imported_at=timezone.now(),
        imported_by=user,
        message=f"{created} created, {skipped} duplicates skipped",
    )
