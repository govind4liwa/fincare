"""DRF serializers for VAT 201 returns, Corporate Tax returns, and tax-code
rate history."""

from rest_framework import serializers

from apps.tax.models import CorporateTaxReturn, TaxCodeRateHistory, TaxReturn, TaxReturnBox


class TaxCodeRateHistorySerializer(serializers.ModelSerializer):
    tax_code_code = serializers.CharField(source="tax_code.code", read_only=True)

    class Meta:
        model = TaxCodeRateHistory
        fields = [
            "id",
            "tax_code",
            "tax_code_code",
            "rate",
            "effective_from",
            "effective_to",
            "note",
        ]


class TaxReturnBoxSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaxReturnBox
        fields = [
            "id",
            "box_code",
            "label",
            "emirate",
            "amount",
            "vat_amount",
            "adjustment",
            "sort_order",
        ]


class TaxReturnSerializer(serializers.ModelSerializer):
    """A draft names its scope (vat_group or entity) and period; `compute`
    derives the GL-authoritative totals and rebuilds the boxes; `file` marks
    it filed. Those derived fields are read-only here."""

    boxes = TaxReturnBoxSerializer(many=True, read_only=True)
    vat_group_name = serializers.CharField(source="vat_group.name", read_only=True)
    entity_name = serializers.CharField(source="entity.legal_name", read_only=True)
    filed_by_email = serializers.EmailField(source="filed_by.email", read_only=True)

    class Meta:
        model = TaxReturn
        fields = [
            "id",
            "vat_group",
            "vat_group_name",
            "entity",
            "entity_name",
            "trn",
            "period_start",
            "period_end",
            "status",
            "total_output_vat",
            "total_input_vat",
            "net_vat_payable",
            "computed_at",
            "filed_at",
            "filed_by_email",
            "filing_reference",
            "boxes",
        ]
        read_only_fields = [
            "trn",
            "status",
            "total_output_vat",
            "total_input_vat",
            "net_vat_payable",
            "computed_at",
            "filed_at",
            "filing_reference",
        ]


class CorporateTaxReturnSerializer(serializers.ModelSerializer):
    """A draft names entity/fiscal_year/period + accounting_net_profit
    (+ optional adjustments/statutory overrides); `compute` derives
    taxable_income/tax_payable; `file` marks it filed."""

    entity_name = serializers.CharField(source="entity.legal_name", read_only=True)
    filed_by_email = serializers.EmailField(source="filed_by.email", read_only=True)

    class Meta:
        model = CorporateTaxReturn
        fields = [
            "id",
            "entity",
            "entity_name",
            "fiscal_year",
            "trn",
            "period_start",
            "period_end",
            "accounting_net_profit",
            "adjustments",
            "taxable_income",
            "zero_band_threshold",
            "tax_rate",
            "small_business_relief",
            "tax_payable",
            "status",
            "computed_at",
            "filed_at",
            "filed_by_email",
            "filing_reference",
        ]
        read_only_fields = [
            "trn",
            "taxable_income",
            "tax_payable",
            "status",
            "computed_at",
            "filed_at",
            "filing_reference",
        ]
