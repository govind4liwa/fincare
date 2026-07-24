"""Report catalog API: build a report and return JSON or Excel.

GET /api/v1/reports/<code>/?entity_id=&period_id=&basis=&export=json|xlsx

Note: the export format uses ``export=`` (not ``format=``) — DRF reserves the
``format`` query param for content negotiation and would 404 on ``xlsx``.
"""

import logging

from django.http import HttpResponse
from django.utils import timezone

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.exports.services.xlsx import report_to_xlsx_bytes
from apps.ledger.models import AccountingPeriod
from apps.reports.models import ReportRun
from apps.reports.services.catalog import build_report
from apps.reports.services.dashboard import dashboard_summary
from apps.tenants.models import Entity
from apps.tenants.views import accessible_entity_ids
from apps.users.permissions import HasAnyRole

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
logger = logging.getLogger(__name__)


class ReportView(APIView):
    permission_classes = [IsAuthenticated, HasAnyRole]
    required_roles = ("accountant", "manager", "admin", "auditor")

    def get(self, request, code):
        entity_ids = [e for e in request.query_params.getlist("entity_id") if e]
        period_id = request.query_params.get("period_id")
        basis = request.query_params.get("basis", "accrual")
        fmt = request.query_params.get("export", "json")
        period = AccountingPeriod.objects.filter(id=period_id).first() if period_id else None

        try:
            report = build_report(code.upper(), entity_ids=entity_ids, period=period, basis=basis)
        except (ValueError, KeyError, TypeError):
            logger.exception("Report generation rejected")
            return Response({"detail": "Invalid report request."}, status=400)

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


class DashboardView(APIView):
    """Headline KPIs for the landing dashboard, scoped to the user's entities.

    GET /api/v1/reports/dashboard/?entity=<id>  (omit entity = all accessible).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        empty = {"revenue": "0.00", "expenses": "0.00", "cash_bank": "0.00", "vat_payable": "0.00"}

        ids = accessible_entity_ids(request.user)  # None = superuser (all entities)
        requested = request.query_params.get("entity")
        if requested:
            if ids is not None and requested not in {str(i) for i in ids}:
                return Response({"detail": "Not found."}, status=404)
            entity_ids = [requested]
        elif ids is None:
            entity_ids = list(Entity.objects.filter(is_active=True).values_list("id", flat=True))
        else:
            entity_ids = list(ids)

        if not entity_ids:
            return Response({"period": None, **empty})

        today = timezone.now().date()
        period = (
            AccountingPeriod.objects.filter(
                entity_id__in=entity_ids, start_date__lte=today, end_date__gte=today
            )
            .order_by("-start_date")
            .first()
            or AccountingPeriod.objects.filter(entity_id__in=entity_ids)
            .order_by("-end_date")
            .first()
        )
        if period is None:
            return Response({"period": None, **empty})

        kpis = dashboard_summary(entity_ids=entity_ids, period=period)
        return Response(
            {
                "period": {
                    "name": period.name,
                    "start": period.start_date,
                    "end": period.end_date,
                },
                "revenue": str(kpis["revenue"]),
                "expenses": str(kpis["expenses"]),
                "cash_bank": str(kpis["cash_bank"]),
                "vat_payable": str(kpis["vat_payable"]),
            }
        )
