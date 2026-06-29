"""Admin for tenancy master data."""

from django.contrib import admin

from apps.tenants.models import (
    Branch,
    BusinessCategory,
    CostCenter,
    Department,
    Entity,
    IntercompanyMap,
    VatGroup,
)


@admin.register(BusinessCategory)
class BusinessCategoryAdmin(admin.ModelAdmin):
    list_display = ("band", "key", "label", "coa_template_key", "is_active")
    ordering = ("band",)
    search_fields = ("key", "label")


@admin.register(VatGroup)
class VatGroupAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "trn", "is_active")
    search_fields = ("code", "name", "trn")


@admin.register(Entity)
class EntityAdmin(admin.ModelAdmin):
    list_display = (
        "numeric_code",
        "legal_name",
        "category",
        "vat_group",
        "accounting_basis",
        "is_active",
    )
    list_filter = ("category", "vat_group", "accounting_basis", "is_active")
    search_fields = ("numeric_code", "code", "legal_name", "trade_name", "corporate_tax_trn")
    autocomplete_fields = ("category", "vat_group", "base_currency", "parent_entity")


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ("entity", "code", "name", "emirate", "is_active")
    list_filter = ("emirate", "is_active")
    search_fields = ("code", "name")


@admin.register(CostCenter)
class CostCenterAdmin(admin.ModelAdmin):
    list_display = ("entity", "code", "name", "parent", "is_active")
    search_fields = ("code", "name")


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("entity", "code", "name", "is_active")
    search_fields = ("code", "name")


@admin.register(IntercompanyMap)
class IntercompanyMapAdmin(admin.ModelAdmin):
    list_display = ("from_entity", "to_entity", "is_active")
