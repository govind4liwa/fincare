"""Multi-entity / multi-branch tenancy models (design doc 01, ADR-0004/0005/0006).

Every transactional table elsewhere carries ``entity`` (FK → Entity). Tenant
isolation is enforced at the DB layer via RLS keyed on ``entity_id`` (ADR-0008).
"""

from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class BusinessCategory(BaseModel):
    """A business type that drives a COA template and a code band (ADR-0004/0005)."""

    key = models.CharField(max_length=32, unique=True)
    label = models.CharField(max_length=64)
    band = models.CharField(max_length=1, unique=True)  # COA band digit 0-9
    coa_template_key = models.CharField(max_length=32)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["band"]
        verbose_name_plural = "business categories"

    def __str__(self):
        return f"{self.band} · {self.label}"


class VatGroup(BaseModel):
    """A UAE VAT group sharing one TRN across member entities (ADR-0006)."""

    code = models.CharField(max_length=16, unique=True)
    name = models.CharField(max_length=128)
    trn = models.CharField(max_length=15, blank=True, null=True, unique=True)
    representative_entity = models.ForeignKey(
        "tenants.Entity",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return self.code


class Entity(BaseModel):
    """A legal company in the group."""

    class AccountingBasis(models.TextChoices):
        CASH = "cash", "Cash"
        ACCRUAL = "accrual", "Accrual"

    code = models.CharField(max_length=16, unique=True)
    numeric_code = models.CharField(max_length=3, unique=True)  # band + sequence
    legal_name = models.CharField(max_length=255)
    trade_name = models.CharField(max_length=255, blank=True)
    category = models.ForeignKey(
        BusinessCategory, on_delete=models.PROTECT, related_name="entities"
    )
    vat_group = models.ForeignKey(
        VatGroup, on_delete=models.SET_NULL, null=True, blank=True, related_name="entities"
    )
    corporate_tax_trn = models.CharField(max_length=20, blank=True)
    licence_no = models.CharField(max_length=64, blank=True)
    base_currency = models.ForeignKey(
        "core.Currency", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    fiscal_year_start_month = models.PositiveSmallIntegerField(default=1)
    accounting_basis = models.CharField(
        max_length=8, choices=AccountingBasis.choices, default=AccountingBasis.ACCRUAL
    )
    parent_entity = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="children"
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["numeric_code"]
        verbose_name_plural = "entities"

    def __str__(self):
        return f"{self.numeric_code} · {self.legal_name}"

    @property
    def effective_trn(self):
        """VAT TRN is resolved from the VAT group, never stored on the entity."""
        return self.vat_group.trn if self.vat_group else None


class Branch(BaseModel):
    entity = models.ForeignKey(Entity, on_delete=models.PROTECT, related_name="branches")
    code = models.CharField(max_length=16)
    name = models.CharField(max_length=128)
    emirate = models.CharField(max_length=32, blank=True)
    address = models.CharField(max_length=512, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["entity", "code"]
        verbose_name_plural = "branches"
        constraints = [
            models.UniqueConstraint(fields=["entity", "code"], name="tenants_branch_unique_code"),
        ]

    def __str__(self):
        return f"{self.entity.numeric_code}/{self.code}"


class CostCenter(BaseModel):
    entity = models.ForeignKey(Entity, on_delete=models.PROTECT, related_name="cost_centers")
    code = models.CharField(max_length=16)
    name = models.CharField(max_length=128)
    parent = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="children"
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["entity", "code"]
        constraints = [
            models.UniqueConstraint(
                fields=["entity", "code"], name="tenants_costcenter_unique_code"
            ),
        ]

    def __str__(self):
        return f"{self.entity.numeric_code}/{self.code}"


class Department(BaseModel):
    entity = models.ForeignKey(Entity, on_delete=models.PROTECT, related_name="departments")
    code = models.CharField(max_length=16)
    name = models.CharField(max_length=128)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["entity", "code"]
        constraints = [
            models.UniqueConstraint(
                fields=["entity", "code"], name="tenants_department_unique_code"
            ),
        ]

    def __str__(self):
        return f"{self.entity.numeric_code}/{self.code}"


class IntercompanyMap(BaseModel):
    """Pairs two entities for intercompany recharge / settlement.

    The due-to / due-from account links (→ ``accounts.Account``) are added in
    Phase 5 when the ``accounts`` app exists.
    """

    from_entity = models.ForeignKey(Entity, on_delete=models.PROTECT, related_name="ic_from")
    to_entity = models.ForeignKey(Entity, on_delete=models.PROTECT, related_name="ic_to")
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["from_entity", "to_entity"], name="tenants_intercompany_unique_pair"
            ),
        ]

    def __str__(self):
        return f"{self.from_entity_id} → {self.to_entity_id}"


class UserEntityMembership(BaseModel):
    """Which entities a user may access. Drives the RLS tenant context (ADR-0008).

    A superuser bypasses this (sees all entities). Everyone else is scoped to
    their active memberships.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="entity_memberships"
    )
    entity = models.ForeignKey(Entity, on_delete=models.CASCADE, related_name="user_memberships")
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "entity"], name="tenants_userentity_unique"),
        ]

    def __str__(self):
        return f"{self.user_id}@{self.entity_id}"
