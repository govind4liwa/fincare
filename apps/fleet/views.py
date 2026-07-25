"""Fleet API: vehicle master, vehicle loans, and versioned EMI schedules.

Schedules are generated as drafts, approved (which locks them), and their
installments posted individually through the ledger engine. Regenerating creates
a new version — posted EMIs are never rewritten.
"""

import logging

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.views import EntityScopedMasterViewSet, scope_to_entities
from apps.fleet.models import LoanSchedule, Vehicle, VehicleLoan, VehicleLoanInstallment
from apps.fleet.serializers import (
    LoanInstallmentSerializer,
    LoanScheduleSerializer,
    VehicleLoanSerializer,
    VehicleSerializer,
)
from apps.fleet.services import schedule as schedule_service
from apps.fleet.services.post import FleetError, post_emi
from apps.users.permissions import ReadAnyWriteRole

logger = logging.getLogger(__name__)
ROLES = ("accountant", "manager", "admin")


class VehicleViewSet(EntityScopedMasterViewSet):
    queryset = Vehicle.objects.all()
    serializer_class = VehicleSerializer
    filterset_fields = ["entity", "ownership", "is_active"]
    ordering_fields = ["code", "make"]
    ordering = ["code"]


class VehicleLoanViewSet(EntityScopedMasterViewSet):
    """Vehicle finance loans. Reads open to members; writes need an accounting role."""

    queryset = VehicleLoan.objects.select_related(
        "vehicle", "loan_account", "interest_account"
    ).prefetch_related("schedules")
    serializer_class = VehicleLoanSerializer
    filterset_fields = ["entity", "vehicle", "is_active", "amortization_method"]
    ordering_fields = ["start_date", "principal"]
    ordering = ["-start_date"]

    @action(detail=True, methods=["post"], url_path="generate-schedule")
    def generate_schedule(self, request, pk=None):
        loan = self.get_object()
        try:
            schedule = schedule_service.generate_schedule(
                loan,
                first_payment_date=request.data.get("first_payment_date") or None,
                note=request.data.get("note", ""),
                user=request.user,
            )
        except (ValueError, ArithmeticError, TypeError):
            logger.exception("Schedule generation failed for loan %s", loan.pk)
            return Response(
                {
                    "detail": "Could not generate the schedule — check the principal, term, "
                    "rate, and first-payment date."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(LoanScheduleSerializer(schedule).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], url_path="schedules")
    def schedules(self, request, pk=None):
        loan = self.get_object()
        rows = loan.schedules.prefetch_related("installments").order_by("-version_no")
        return Response({"schedules": LoanScheduleSerializer(rows, many=True).data})


class LoanScheduleViewSet(viewsets.ReadOnlyModelViewSet):
    """Generated schedule versions. Approval locks a version; drafts can be discarded."""

    serializer_class = LoanScheduleSerializer
    permission_classes = [IsAuthenticated, ReadAnyWriteRole]
    required_roles = ROLES
    filterset_fields = ["loan", "status", "method"]
    ordering_fields = ["version_no"]
    ordering = ["-version_no"]

    def get_queryset(self):
        return scope_to_entities(
            LoanSchedule.objects.select_related("loan").prefetch_related("installments"),
            self.request.user,
            "loan__entity_id",
        )

    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        schedule = self.get_object()
        try:
            schedule_service.approve_schedule(schedule, user=request.user)
        except (ValueError, TypeError):
            logger.warning("Schedule approval rejected for %s", schedule.pk)
            return Response(
                {"detail": "Only a draft schedule can be approved."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(self.get_serializer(schedule).data)

    @action(detail=True, methods=["post"], url_path="discard")
    def discard(self, request, pk=None):
        schedule = self.get_object()
        try:
            schedule_service.discard_schedule(schedule, user=request.user)
        except (ValueError, TypeError):
            logger.warning("Schedule discard rejected for %s", schedule.pk)
            return Response(
                {"detail": "Only a draft schedule with no posted instalments can be " "discarded."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class LoanInstallmentViewSet(viewsets.ReadOnlyModelViewSet):
    """EMI instalments. `post` books DR Loan Payable / DR Interest / CR Bank."""

    serializer_class = LoanInstallmentSerializer
    permission_classes = [IsAuthenticated, ReadAnyWriteRole]
    required_roles = ROLES
    filterset_fields = ["loan", "schedule", "status"]
    ordering_fields = ["due_date", "installment_no"]
    ordering = ["installment_no"]

    def get_queryset(self):
        return scope_to_entities(
            VehicleLoanInstallment.objects.select_related("loan", "schedule", "bank_account"),
            self.request.user,
            "loan__entity_id",
        )

    @action(detail=True, methods=["post"], url_path="post")
    def post_installment(self, request, pk=None):
        installment = self.get_object()
        bank_account = request.data.get("bank_account")
        if bank_account:
            installment.bank_account_id = bank_account
            installment.save(update_fields=["bank_account", "updated_at"])
        try:
            post_emi(installment, user=request.user)
        except FleetError:
            logger.exception("EMI posting failed for installment %s", installment.pk)
            return Response(
                {
                    "detail": "Could not post this instalment — it must be draft, on an "
                    "approved schedule, with a bank account."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(self.get_serializer(installment).data)
