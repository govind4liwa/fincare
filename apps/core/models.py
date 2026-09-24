"""Core abstract models and shared primitives for FinCare.

Conventions (CLAUDE.md §4, design doc 01):
- UUID primary keys, audit fields, soft delete on every persistent model.
- Money uses Decimal; rates use 6 decimal places.

Forward-dependency strategy (see ADR-0009):
- ``created_by`` / ``updated_by`` reference ``settings.AUTH_USER_MODEL`` (set to
  ``users.User`` in Phase 2), so core never imports the user app.
- ``NumberSequence.entity_id`` / ``Attachment.entity_id`` are intentionally plain
  UUID scope keys, NOT FKs, so ``core`` stays at the root of the dependency graph
  (it must not depend on ``tenants``, which depends on ``core``). Tenant isolation
  is enforced by RLS on the ``entity_id`` column (ADR-0008); referential validity
  is a service-layer responsibility. This is final, not a pending promotion.
"""

import uuid

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone

from apps.core.managers import AllObjectsManager, SoftDeleteManager


class PostedRowProtectedError(ValueError):
    """Raised when a document that has entered the accounting record is deleted.

    A subclass of ``ValueError`` so existing ``except ValueError`` handlers
    around model writes keep working.
    """


class BaseModel(models.Model):
    """Abstract base: UUID pk, audit trail, soft delete.

    Subclasses that post to the general ledger set ``DELETE_PROTECTED_STATUSES``
    to the statuses after which the row is part of the accounting record. Once a
    row reaches one of those, ``delete()`` and ``hard_delete()`` refuse
    (CLAUDE.md §4.5 — corrections go through a reversal or credit note, never a
    deletion). Drafts stay deletable.
    """

    #: Statuses after which this row may not be deleted by any path. Empty for
    #: masters and reference data, which are deactivated rather than posted.
    DELETE_PROTECTED_STATUSES: tuple[str, ...] = ()

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        editable=False,
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        editable=False,
    )
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = SoftDeleteManager()
    all_objects = AllObjectsManager()

    class Meta:
        abstract = True
        base_manager_name = "all_objects"

    def _assert_deletable(self):
        """Refuse deletion once the row is part of the accounting record.

        Two independent tests, because neither alone is sufficient:

        * A linked ``journal_entry`` means this document has hit the general
          ledger, whatever its status is called. ``payroll.Advance`` stays
          ``open`` after it posts, so a status check alone would miss it.
        * ``DELETE_PROTECTED_STATUSES`` covers rows that are part of the record
          without a journal entry of their own — a filed tax return, a completed
          reconciliation, an approved loan schedule, a closed period.
        """
        if getattr(self, "journal_entry_id", None) is not None:
            raise PostedRowProtectedError(
                f"{type(self).__name__} {self.pk} has posted to the general ledger "
                "and cannot be deleted. Reverse it instead."
            )
        status = getattr(self, "status", None)
        if status is not None and status in self.DELETE_PROTECTED_STATUSES:
            raise PostedRowProtectedError(
                f"{type(self).__name__} {self.pk} is {status} and cannot be deleted. "
                "Reverse it or raise a credit/debit note instead."
            )

    def delete(self, using=None, keep_parents=False):
        """Soft delete: flag the row instead of removing it."""
        self._assert_deletable()
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(using=using, update_fields=["is_deleted", "deleted_at", "updated_at"])

    def hard_delete(self, using=None, keep_parents=False):
        """Permanently remove the row (escape hatch).

        Guarded too: a posted row must not be removable by a shortcut that
        exists for cleaning up drafts and test data.
        """
        self._assert_deletable()
        return super().delete(using=using, keep_parents=keep_parents)


class Currency(BaseModel):
    """ISO 4217 currency. Default group base is AED."""

    code = models.CharField(max_length=3, unique=True)
    name = models.CharField(max_length=64)
    symbol = models.CharField(max_length=8)
    decimal_places = models.PositiveSmallIntegerField(default=2)
    is_base = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]
        verbose_name_plural = "currencies"
        constraints = [
            # At most one row may have is_base=True.
            models.UniqueConstraint(
                fields=["is_base"],
                condition=models.Q(is_base=True),
                name="core_currency_single_base",
            ),
        ]

    def __str__(self):
        return self.code


class ExchangeRate(BaseModel):
    """FX rate between two currencies on a given date."""

    from_currency = models.ForeignKey(Currency, on_delete=models.PROTECT, related_name="rates_from")
    to_currency = models.ForeignKey(Currency, on_delete=models.PROTECT, related_name="rates_to")
    rate = models.DecimalField(max_digits=18, decimal_places=6)
    rate_date = models.DateField(db_index=True)
    source = models.CharField(max_length=32, blank=True)

    class Meta:
        ordering = ["-rate_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["from_currency", "to_currency", "rate_date"],
                name="core_exchangerate_unique_pair_date",
            ),
        ]

    def __str__(self):
        return f"{self.from_currency_id}->{self.to_currency_id} @ {self.rate_date}"


class NumberSequence(BaseModel):
    """Gap-safe document numbering, scoped per entity + series + period.

    ``entity_id`` is a UUID scope key (not a FK — see ADR-0009).
    Allocation goes through ``apps.core.services.sequences``.
    """

    class ResetPolicy(models.TextChoices):
        NEVER = "never", "Never"
        YEARLY = "yearly", "Yearly"
        MONTHLY = "monthly", "Monthly"

    entity_id = models.UUIDField(db_index=True)
    code = models.CharField(max_length=32)
    prefix = models.CharField(max_length=16, blank=True)
    suffix = models.CharField(max_length=16, blank=True)
    padding = models.PositiveSmallIntegerField(default=6)
    next_value = models.BigIntegerField(default=1)
    reset_policy = models.CharField(
        max_length=16, choices=ResetPolicy.choices, default=ResetPolicy.NEVER
    )
    period_key = models.CharField(max_length=7, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["entity_id", "code", "period_key"],
                name="core_numbersequence_unique_scope",
            ),
        ]

    def __str__(self):
        return f"{self.code}[{self.entity_id}/{self.period_key or '-'}]"

    def format(self, value):
        """Render a numeric value into the full document number string."""
        return f"{self.prefix}{str(value).zfill(self.padding)}{self.suffix}"


class Attachment(BaseModel):
    """Generic file attachment for any document.

    ``entity_id`` is a UUID scope key (not a FK — see ADR-0009).
    """

    entity_id = models.UUIDField(db_index=True)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.UUIDField(db_index=True)
    content_object = GenericForeignKey("content_type", "object_id")
    file = models.FileField(upload_to="attachments/%Y/%m/", max_length=512)
    original_name = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=128, blank=True)
    size_bytes = models.BigIntegerField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
        ]

    def __str__(self):
        return self.original_name
