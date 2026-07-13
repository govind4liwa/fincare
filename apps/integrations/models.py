"""Integrations module — file importers for bank statements & platform earnings.

An ``ImportProfile`` holds the per-source column mapping (a bank's statement layout
or a ride-hailing platform's earnings export) so new formats need only config, not
code. Each import is logged as an ``ImportBatch`` (filename, file hash, row counts,
status) for traceability and idempotent re-import. Parsed rows land in the owning
module's staging tables: ``banking.StatementLine`` and ``platforms.EarningImport``.
"""

from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class ImportKind(models.TextChoices):
    BANK_STATEMENT = "bank_statement", "Bank statement"
    PLATFORM_EARNING = "platform_earning", "Platform earning"


class ImportProfile(BaseModel):
    """Column mapping + parse options for one source (a bank or a platform).

    ``column_map`` maps canonical target fields to the source file's column headers,
    e.g. {"txn_date": "Date", "deposit": "Credit", "withdrawal": "Debit"}.
    """

    entity = models.ForeignKey(
        "tenants.Entity",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="import_profiles",
    )
    kind = models.CharField(max_length=20, choices=ImportKind.choices)
    name = models.CharField(max_length=128)
    source_key = models.CharField(max_length=64)  # bank code / platform name
    column_map = models.JSONField(default=dict)
    date_format = models.CharField(max_length=32, blank=True)  # e.g. "%d/%m/%Y"; blank = auto
    skip_rows = models.PositiveSmallIntegerField(default=0)  # header noise before the table
    sheet = models.CharField(max_length=64, blank=True)  # xlsx sheet name (blank = first)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["kind", "source_key"]
        constraints = [
            models.UniqueConstraint(
                fields=["entity", "kind", "source_key"],
                name="integrations_profile_unique_source",
            ),
        ]

    def __str__(self):
        return f"{self.kind}:{self.source_key}"


class ImportBatch(BaseModel):
    """Log of a single import run (idempotency + audit)."""

    class Status(models.TextChoices):
        DONE = "done", "Done"
        ERROR = "error", "Error"

    entity = models.ForeignKey(
        "tenants.Entity", on_delete=models.PROTECT, related_name="import_batches"
    )
    profile = models.ForeignKey(
        ImportProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name="batches"
    )
    kind = models.CharField(max_length=20, choices=ImportKind.choices)
    filename = models.CharField(max_length=255)
    file_hash = models.CharField(max_length=64, blank=True, db_index=True)  # sha256
    bank_account = models.ForeignKey(
        "banking.BankAccount", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    platform = models.ForeignKey(
        "platforms.Platform", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    bank_statement = models.ForeignKey(
        "banking.BankStatement", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    row_count = models.PositiveIntegerField(default=0)
    created_count = models.PositiveIntegerField(default=0)
    skipped_count = models.PositiveIntegerField(default=0)  # duplicates (idempotent re-import)
    error_count = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DONE)
    message = models.CharField(max_length=512, blank=True)
    imported_at = models.DateTimeField(null=True, blank=True)
    imported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.kind} {self.filename} (+{self.created_count}/~{self.skipped_count})"
