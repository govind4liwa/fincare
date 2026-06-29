"""Soft-delete managers and querysets for FinCare core models."""

from django.db import models
from django.utils import timezone


class SoftDeleteQuerySet(models.QuerySet):
    """QuerySet whose ``delete()`` performs a soft delete."""

    def delete(self):
        """Soft-delete every row in the queryset."""
        return super().update(is_deleted=True, deleted_at=timezone.now())

    def hard_delete(self):
        """Permanently remove rows (escape hatch — use sparingly)."""
        return super().delete()

    def alive(self):
        return self.filter(is_deleted=False)

    def dead(self):
        return self.filter(is_deleted=True)


class SoftDeleteManager(models.Manager):
    """Default manager: hides soft-deleted rows."""

    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db).filter(is_deleted=False)


class AllObjectsManager(models.Manager):
    """Unfiltered manager: includes soft-deleted rows. Used as base_manager."""

    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db)
