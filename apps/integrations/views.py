"""Integrations API: import profiles (per-source column mappings) and import
batches — the run log plus the two multipart upload actions that drive the
file importers (bank statements → banking.StatementLine, platform earnings →
platforms.EarningImport)."""

import logging

from django.db.models import Q

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.views import scope_to_entities
from apps.banking.models import BankAccount
from apps.integrations.models import ImportBatch, ImportKind, ImportProfile
from apps.integrations.serializers import (
    BankStatementUploadSerializer,
    ImportBatchSerializer,
    ImportProfileSerializer,
    PlatformEarningsUploadSerializer,
)
from apps.integrations.services.bank import import_bank_statement
from apps.integrations.services.log import record_failed_import
from apps.integrations.services.parsers import IntegrationError
from apps.integrations.services.platform import import_platform_earnings
from apps.platforms.models import Platform
from apps.tenants.views import accessible_entity_ids
from apps.users.permissions import ReadAnyWriteRole

logger = logging.getLogger(__name__)
ROLES = ("accountant", "manager", "admin")

IMPORT_FAILED_DETAIL = (
    "Import failed — the file could not be processed with the selected profile. "
    "The reason is recorded on the batch log."
)


class ImportProfileViewSet(viewsets.ModelViewSet):
    """Column-mapping masters. A profile with no entity is group-wide and
    visible to every member; entity-scoped ones follow the usual scoping.
    Masters are deactivated, never deleted."""

    serializer_class = ImportProfileSerializer
    permission_classes = [IsAuthenticated, ReadAnyWriteRole]
    required_roles = ROLES
    http_method_names = ["get", "post", "put", "patch", "head", "options"]
    filterset_fields = ["entity", "kind", "source_key", "is_active"]
    ordering_fields = ["kind", "name", "source_key"]
    ordering = ["kind", "source_key"]

    def get_queryset(self):
        ids = accessible_entity_ids(self.request.user)
        qs = ImportProfile.objects.select_related("entity")
        if ids is None:
            return qs
        return qs.filter(Q(entity_id__in=ids) | Q(entity__isnull=True))


class ImportBatchViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only import run log, plus the two upload actions."""

    serializer_class = ImportBatchSerializer
    permission_classes = [IsAuthenticated, ReadAnyWriteRole]
    required_roles = ROLES
    filterset_fields = ["entity", "kind", "status", "bank_account", "platform", "profile"]
    ordering_fields = ["created_at", "imported_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return scope_to_entities(
            ImportBatch.objects.select_related(
                "profile", "bank_account", "platform", "imported_by"
            ),
            self.request.user,
        )

    def _get_profile(self, pk, kind, entity):
        ids = accessible_entity_ids(self.request.user)
        qs = ImportProfile.objects.all()
        if ids is not None:
            qs = qs.filter(Q(entity_id__in=ids) | Q(entity__isnull=True))
        profile = qs.filter(pk=pk).first()
        if profile is None:
            raise ValidationError({"profile": "Not found."})
        if not profile.is_active:
            raise ValidationError({"profile": "This profile is inactive."})
        if profile.kind != kind:
            raise ValidationError({"profile": "This profile is for a different import kind."})
        if profile.entity_id is not None and profile.entity_id != entity.id:
            raise ValidationError({"profile": "This profile belongs to a different entity."})
        return profile

    @action(
        detail=False,
        methods=["post"],
        url_path="bank-statement",
        parser_classes=[MultiPartParser, FormParser],
    )
    def bank_statement(self, request):
        serializer = BankStatementUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        bank_account = (
            scope_to_entities(BankAccount.objects.select_related("entity"), request.user)
            .filter(pk=data["bank_account"], is_active=True)
            .first()
        )
        if bank_account is None:
            raise ValidationError({"bank_account": "Not found."})
        profile = self._get_profile(data["profile"], ImportKind.BANK_STATEMENT, bank_account.entity)

        upload = data["file"]
        content = upload.read()
        try:
            batch = import_bank_statement(
                bank_account=bank_account,
                profile=profile,
                content=content,
                filename=upload.name,
                statement_no=data.get("statement_no", ""),
                user=request.user,
            )
        except IntegrationError as exc:
            logger.warning("Bank statement import of %r failed: %s", upload.name, exc)
            failed = record_failed_import(
                entity=bank_account.entity,
                kind=ImportKind.BANK_STATEMENT,
                filename=upload.name,
                content=content,
                message=exc,
                profile=profile,
                bank_account=bank_account,
                user=request.user,
            )
            return Response(
                {"detail": IMPORT_FAILED_DETAIL, "batch": str(failed.id)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(self.get_serializer(batch).data, status=status.HTTP_201_CREATED)

    @action(
        detail=False,
        methods=["post"],
        url_path="platform-earnings",
        parser_classes=[MultiPartParser, FormParser],
    )
    def platform_earnings(self, request):
        serializer = PlatformEarningsUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        platform = (
            scope_to_entities(Platform.objects.select_related("entity"), request.user)
            .filter(pk=data["platform"], is_active=True)
            .first()
        )
        if platform is None:
            raise ValidationError({"platform": "Not found."})
        profile = self._get_profile(data["profile"], ImportKind.PLATFORM_EARNING, platform.entity)

        upload = data["file"]
        content = upload.read()
        try:
            batch = import_platform_earnings(
                platform=platform,
                profile=profile,
                content=content,
                filename=upload.name,
                user=request.user,
            )
        except IntegrationError as exc:
            logger.warning("Platform earnings import of %r failed: %s", upload.name, exc)
            failed = record_failed_import(
                entity=platform.entity,
                kind=ImportKind.PLATFORM_EARNING,
                filename=upload.name,
                content=content,
                message=exc,
                profile=profile,
                platform=platform,
                user=request.user,
            )
            return Response(
                {"detail": IMPORT_FAILED_DETAIL, "batch": str(failed.id)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(self.get_serializer(batch).data, status=status.HTTP_201_CREATED)
