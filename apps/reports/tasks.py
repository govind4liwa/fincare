"""Celery tasks for scheduled report generation (design doc 05)."""

from django.utils import timezone

from celery import shared_task

from apps.ledger.models import AccountingPeriod
from apps.reports.models import ReportRun, ReportSchedule
from apps.reports.services.catalog import build_report


@shared_task
def run_scheduled_report(schedule_id):
    """Generate a scheduled report and log a ReportRun. Returns the run id."""
    schedule = ReportSchedule.objects.get(id=schedule_id)
    run = ReportRun.objects.create(
        entity_scope=schedule.entity_scope,
        entity=schedule.entity,
        report_code=schedule.report_code,
        params=schedule.params,
        format=schedule.format,
        status=ReportRun.Status.QUEUED,
    )
    try:
        params = dict(schedule.params)
        period_id = params.pop("period_id", None)
        period = AccountingPeriod.objects.get(id=period_id) if period_id else None
        entity_ids = params.pop("entity_ids", None) or (
            [schedule.entity_id] if schedule.entity_id else []
        )
        build_report(schedule.report_code, entity_ids=entity_ids, period=period, **params)
        run.status = ReportRun.Status.DONE
        run.generated_at = timezone.now()
    except Exception as exc:  # log failure on the run row, never crash the worker
        run.status = ReportRun.Status.ERROR
        run.file_ref = str(exc)[:512]
    run.save(update_fields=["status", "generated_at", "file_ref", "updated_at"])
    return str(run.id)
