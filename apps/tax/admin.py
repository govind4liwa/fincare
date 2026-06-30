"""Admin for the Tax module (VAT 201 + Corporate Tax)."""

from django.contrib import admin

from apps.tax.models import CorporateTaxReturn, TaxCodeRateHistory, TaxReturn, TaxReturnBox


@admin.register(TaxCodeRateHistory)
class TaxCodeRateHistoryAdmin(admin.ModelAdmin):
    list_display = ("tax_code", "rate", "effective_from", "effective_to")
    list_filter = ("tax_code",)
    date_hierarchy = "effective_from"


class TaxReturnBoxInline(admin.TabularInline):
    model = TaxReturnBox
    extra = 0
    readonly_fields = ("box_code", "label", "emirate", "amount", "vat_amount", "sort_order")
    can_delete = False


@admin.register(TaxReturn)
class TaxReturnAdmin(admin.ModelAdmin):
    list_display = (
        "__str__",
        "vat_group",
        "entity",
        "period_start",
        "period_end",
        "total_output_vat",
        "total_input_vat",
        "net_vat_payable",
        "status",
    )
    list_filter = ("status", "vat_group", "entity")
    date_hierarchy = "period_end"
    inlines = [TaxReturnBoxInline]
    readonly_fields = (
        "trn",
        "total_output_vat",
        "total_input_vat",
        "net_vat_payable",
        "computed_at",
        "filed_at",
        "filed_by",
    )


@admin.register(CorporateTaxReturn)
class CorporateTaxReturnAdmin(admin.ModelAdmin):
    list_display = (
        "entity",
        "fiscal_year",
        "accounting_net_profit",
        "taxable_income",
        "tax_payable",
        "small_business_relief",
        "status",
    )
    list_filter = ("status", "small_business_relief", "fiscal_year", "entity")
    readonly_fields = (
        "taxable_income",
        "tax_payable",
        "trn",
        "computed_at",
        "filed_at",
        "filed_by",
    )
