"""Report catalog API: build a report and return JSON, Excel or PDF.

GET /api/v1/reports/<code>/?entity_id=&period_id=&basis=&format=json|xlsx|pdf
"""

from django.http import HttpResponse
from django.utils import timezone

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.exports.services.xlsx import report_to_xlsx_bytes
from apps.ledger.models import AccountingPeriod
from apps.reports.models import ReportRun
from apps.reports.services.catalog import build_report
from apps.users.permissions import HasAnyRole

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class ReportView(APIView):
    permission_classes = [IsAuthenticated, HasAnyRole]
    required_roles = ("accountant", "manager", "admin", "auditor")

    def get(self, request, code):
        entity_ids = [e for e in request.query_params.getlist("entity_id") if e]
        period_id = request.query_params.get("period_id")
        basis = request.query_params.get("basis", "accrual")
        fmt = request.query_params.get("format", "json")
        period = AccountingPeriod.objects.filter(id=period_id).first() if period_id else None

        try:
            report = build_report(code.upper(), entity_ids=entity_ids, period=period, basis=basis)
        except (ValueError, KeyError, TypeError) as exc:
            return Response({"detail": str(exc)}, status=400)

        run = ReportRun.objects.create(
            entity_scope=ReportRun.Scope.GROUP if len(entity_ids) > 1 else ReportRun.Scope.ENTITY,
            entity_id=entity_ids[0] if len(entity_ids) == 1 else None,
            report_code=code.upper(),
            params={"entity_ids": entity_ids, "period_id": period_id, "basis": basis},
            format=fmt,
            status=ReportRun.Status.DONE,
            generated_at=timezone.now(),
            generated_by=request.user,
        )

        if fmt == "xlsx":
            resp = HttpResponse(report_to_xlsx_bytes(report), content_type=XLSX_MIME)
            resp["Content-Disposition"] = f'attachment; filename="{code.upper()}.xlsx"'
            return resp
        return Response({"report": report, "run_id": str(run.id)})
