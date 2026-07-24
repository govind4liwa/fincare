"""DRF serializers for tenancy resources (entities, branches)."""

from rest_framework import serializers

from apps.tenants.models import Branch, BusinessCategory, Entity, VatGroup


class BusinessCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = BusinessCategory
        fields = ["id", "key", "label", "band"]


class VatGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = VatGroup
        fields = ["id", "code", "name", "trn"]


class EntitySerializer(serializers.ModelSerializer):
    category = BusinessCategorySerializer(read_only=True)
    vat_group = VatGroupSerializer(read_only=True)
    effective_trn = serializers.ReadOnlyField()

    class Meta:
        model = Entity
        fields = [
            "id",
            "code",
            "numeric_code",
            "legal_name",
            "trade_name",
            "category",
            "vat_group",
            "corporate_tax_trn",
            "licence_no",
            "fiscal_year_start_month",
            "accounting_basis",
            "parent_entity",
            "is_active",
            "effective_trn",
        ]


class BranchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = ["id", "entity", "code", "name", "emirate", "address", "is_active"]
