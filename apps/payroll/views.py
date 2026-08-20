"""Payroll API: salary components, employees + salary structure, the
run -> payslip lifecycle (build -> post accrual -> pay), salary advances,
and WPS/SIF batch generation + export.

Gratuity/leave is a separate follow-up slice.
"""

import logging

from django.db.models import Q
from django.http import HttpResponse

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.views import EntityScopedMasterViewSet, scope_to_entities
from apps.banking.models import BankAccount
from apps.payroll.models import (
    Advance,
    Employee,
    EmployeeSalary,
    Payslip,
    Run,
    SalaryComponent,
    WpsBatch,
)
from apps.payroll.serializers import (
    AdvanceSerializer,
    EmployeeSalarySerializer,
    EmployeeSerializer,
    PayslipSerializer,
    RunSerializer,
    SalaryComponentSerializer,
    WpsBatchSerializer,
)
from apps.payroll.services.advance import pay_advance
from apps.payroll.services.engine import PayrollError
from apps.payroll.services.run import build_run, pay_run, post_run
from apps.payroll.services.wps import export_sif
from apps.tenants.views import accessible_entity_ids
from apps.users.permissions import ReadAnyWriteRole

logger = logging.getLogger(__name__)
ROLES = ("accountant", "manager", "admin")


class SalaryComponentViewSet(viewsets.ModelViewSet):
    """Entity-scoped or group-wide default (entity=null) — a plain entity_id__in
    filter would hide group-wide rows entirely, so scoping is explicit here."""

    serializer_class = SalaryComponentSerializer
    permission_classes = [IsAuthenticated, ReadAnyWriteRole]
    required_roles = ROLES
    filterset_fields = ["entity", "component_type", "is_active"]
    ordering_fields = ["code"]
    ordering = ["code"]

    def get_queryset(self):
        qs = SalaryComponent.objects.select_related("account")
        ids = accessible_entity_ids(self.request.user)
        if ids is None:
            return qs
        return qs.filter(Q(entity_id__in=ids) | Q(entity__isnull=True))


class EmployeeViewSet(EntityScopedMasterViewSet):
    queryset = Employee.objects.select_related(
        "driver", "department", "payable_account"
    ).prefetch_related("salary__component")
    serializer_class = EmployeeSerializer
    filterset_fields = ["entity", "status", "pay_method", "department"]
    ordering_fields = ["code", "name"]
    ordering = ["code"]


class EmployeeSalaryViewSet(EntityScopedMasterViewSet):
    """Effective-dated salary structure rows. Entity-scoped through the employee."""

    queryset = EmployeeSalary.objects.select_related("employee", "component")
    serializer_class = EmployeeSalarySerializer
    entity_field = "employee__entity_id"
    filterset_fields = ["employee", "component"]
    ordering_fields = ["effective_from"]
    ordering = ["-effective_from"]


class RunViewSet(EntityScopedMasterViewSet):
    queryset = Run.objects.select_related("entity", "period", "journal_entry", "payment_entry")
    serializer_class = RunSerializer
    filterset_fields = ["entity", "status", "salary_month"]
    ordering_fields = ["salary_month", "run_date"]
    ordering = ["-salary_month"]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.action in ("retrieve", "list"):
            return qs.prefetch_related("payslips__lines__component", "payslips__employee")
        return qs

    @action(detail=True, methods=["post"], url_path="build")
    def build_action(self, request, pk=None):
        run = self.get_object()
        try:
            build_run(run, user=request.user)
        except PayrollError:
            logger.exception("Payroll run build failed for %s", run.pk)
            return Response(
                {"detail": "Could not build the run — it must be a draft."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(self.get_serializer(run).data)

    @action(detail=True, methods=["post"], url_path="post")
    def post_action(self, request, pk=None):
        run = self.get_object()
        try:
            post_run(run, user=request.user)
        except PayrollError:
            logger.exception("Payroll run post failed for %s", run.pk)
            return Response(
                {
                    "detail": "Could not post — build the run first, and every earning/"
                    "deduction component needs a GL account."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(self.get_serializer(run).data)

    @action(detail=True, methods=["post"], url_path="pay")
    def pay_action(self, request, pk=None):
        run = self.get_object()
        bank_account = scope_to_entities(
            BankAccount.objects.filter(id=request.data.get("bank_account")),
            request.user,
        ).first()
        if bank_account is None:
            return Response(
                {"detail": "bank_account is required."}, status=status.HTTP_400_BAD_REQUEST
            )
        try:
            pay_run(run, bank_account=bank_account, user=request.user)
        except PayrollError:
            logger.exception("Payroll run payment failed for %s", run.pk)
            return Response(
                {"detail": "Could not pay — only a posted (accrued) run can be paid."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(self.get_serializer(run).data)


class AdvanceViewSet(EntityScopedMasterViewSet):
    queryset = Advance.objects.select_related("employee", "advance_account", "bank_account")
    serializer_class = AdvanceSerializer
    filterset_fields = ["entity", "employee", "status"]
    ordering_fields = ["advance_date"]
    ordering = ["-advance_date"]

    @action(detail=True, methods=["post"], url_path="pay")
    def pay_action(self, request, pk=None):
        advance = self.get_object()
        try:
            pay_advance(advance, user=request.user)
        except PayrollError:
            logger.exception("Advance payment failed for %s", advance.pk)
            return Response(
                {
                    "detail": "Could not pay — the advance must be open and unpaid, with a "
                    "bank account and a positive amount."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(self.get_serializer(advance).data)


class WpsBatchViewSet(viewsets.ModelViewSet):
    """A draft names run/employer_eid/employer_bank_routing; `generate_wps`
    derives one record per WPS-paid employee from that run's payslips."""

    serializer_class = WpsBatchSerializer
    permission_classes = [IsAuthenticated, ReadAnyWriteRole]
    required_roles = ROLES
    http_method_names = ["get", "post", "head", "options"]
    filterset_fields = ["run", "status"]
    ordering_fields = ["generated_at"]
    ordering = ["-generated_at"]

    def get_queryset(self):
        return scope_to_entities(
            WpsBatch.objects.select_related("run").prefetch_related("records__employee"),
            self.request.user,
            "run__entity_id",
        )

    @action(detail=True, methods=["get"], url_path="export")
    def export_action(self, request, pk=None):
        batch = self.get_object()
        try:
            content = export_sif(batch)
        except PayrollError:
            logger.exception("SIF export failed for WPS batch %s", batch.pk)
            return Response(
                {"detail": "Could not export — the batch totals do not reconcile."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        response = HttpResponse(content, content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{batch.sif_file_ref}"'
        return response


class PayslipViewSet(viewsets.ReadOnlyModelViewSet):
    """Payslips are a byproduct of RunViewSet.build — read-only here."""

    serializer_class = PayslipSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["run", "employee", "status"]
    ordering_fields = ["employee"]
    ordering = ["employee"]

    def get_queryset(self):
        return scope_to_entities(
            Payslip.objects.select_related("employee", "run").prefetch_related("lines__component"),
            self.request.user,
            "run__entity_id",
        )
