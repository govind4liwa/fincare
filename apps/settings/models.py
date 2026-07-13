"""Per-entity configuration (design doc 01 — indicative set).

Holds fiscal/VAT/numbering/feature configuration keyed per entity (or group-wide
when ``entity`` is null). Values are JSON so config can evolve without schema
churn; typed accessors live in the service layer.
"""

from django.db import models

from apps.core.models import BaseModel


class EntitySetting(BaseModel):
    """Generic per-entity key/value setting (fiscal year, defaults, etc.)."""

    entity = models.ForeignKey("tenants.Entity", on_delete=models.CASCADE, related_name="settings")
    key = models.CharField(max_length=64)
    value = models.JSONField(default=dict)

    class Meta:
        ordering = ["entity", "key"]
        constraints = [
            models.UniqueConstraint(fields=["entity", "key"], name="settings_entitysetting_unique"),
        ]

    def __str__(self):
        return f"{self.entity_id}:{self.key}"


class NumberingSeries(BaseModel):
    """Document numbering configuration per entity + document type."""

    entity = models.ForeignKey(
        "tenants.Entity", on_delete=models.CASCADE, related_name="numbering_series"
    )
    doc_type = models.CharField(max_length=24)
    format = models.CharField(max_length=64)  # e.g. "INV-{seq:06d}"
    reset_policy = models.CharField(max_length=16, default="never")

    class Meta:
        ordering = ["entity", "doc_type"]
        verbose_name_plural = "numbering series"
        constraints = [
            models.UniqueConstraint(
                fields=["entity", "doc_type"], name="settings_numberingseries_unique"
            ),
        ]

    def __str__(self):
        return f"{self.entity_id}:{self.doc_type}"


class VatConfig(BaseModel):
    """Effective-dated VAT/CT parameters; entity-null rows apply group-wide."""

    entity = models.ForeignKey(
        "tenants.Entity",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="vat_config",
    )
    key = models.CharField(max_length=64)
    value = models.JSONField(default=dict)
    effective_from = models.DateField()

    class Meta:
        ordering = ["entity", "key", "-effective_from"]
        verbose_name = "VAT config"
        verbose_name_plural = "VAT config"

    def __str__(self):
        return f"{self.key}@{self.effective_from}"


class FeatureFlag(BaseModel):
    """Per-entity (or global, when entity is null) feature toggle."""

    entity = models.ForeignKey(
        "tenants.Entity",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="feature_flags",
    )
    flag = models.CharField(max_length=64)
    enabled = models.BooleanField(default=False)

    class Meta:
        ordering = ["entity", "flag"]
        constraints = [
            models.UniqueConstraint(
                fields=["entity", "flag"],
                name="settings_featureflag_unique",
            ),
        ]

    def __str__(self):
        return f"{self.flag}={self.enabled}"
