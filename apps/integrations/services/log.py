"""Record failed import runs as ERROR ``ImportBatch`` rows.

A parse/validation failure rolls back the importer's atomic block, so nothing
lands in staging — but the attempt itself must still be visible ("bad rows
reported, not silently dropped"). The batch log carries the reason; the HTTP
error response stays generic.
"""

from django.utils import timezone

from apps.integrations.models import ImportBatch
from apps.integrations.services.parsers import file_hash


def record_failed_import(
    *,
    entity,
    kind,
    filename,
    content,
    message,
    profile=None,
    bank_account=None,
    platform=None,
    user=None,
):
    return ImportBatch.objects.create(
        entity=entity,
        profile=profile,
        kind=kind,
        filename=filename,
        file_hash=file_hash(content),
        bank_account=bank_account,
        platform=platform,
        error_count=1,
        status=ImportBatch.Status.ERROR,
        message=str(message)[:512],
        imported_at=timezone.now(),
        imported_by=user,
    )
