"""DRF serializers for cashbook: cash accounts, petty-cash floats,
replenishments, and cash counts."""

from rest_framework import serializers

from apps.cashbook.models import CashAccount, CashCount, Denomination, PettyCashFloat, Replenishment


class CashAccountSerializer(serializers.ModelSerializer):
    gl_account_code = serializers.CharField(source="gl_account.code", read_only=True)
    gl_account_name = serializers.CharField(source="gl_account.name", read_only=True)

    class Meta:
        model = CashAccount
        fields = [
            "id",
            "entity",
            "code",
            "name",
            "gl_account",
            "gl_account_code",
            "gl_account_name",
            "branch",
            "is_active",
        ]


class PettyCashFloatSerializer(serializers.ModelSerializer):
    cash_account_code = serializers.CharField(source="cash_account.code", read_only=True)

    class Meta:
        model = PettyCashFloat
        fields = [
            "id",
            "entity",
            "cash_account",
            "cash_account_code",
            "code",
            "float_amount",
            "custodian",
            "is_active",
        ]


class ReplenishmentSerializer(serializers.ModelSerializer):
    """A draft names entity/petty_cash_float/bank_account/replenish_date/amount
    (+ optional reference); `post` books DR Petty Cash / CR Bank."""

    cash_account_code = serializers.CharField(
        source="petty_cash_float.cash_account.code", read_only=True
    )

    class Meta:
        model = Replenishment
        fields = [
            "id",
            "entity",
            "petty_cash_float",
            "cash_account_code",
            "bank_account",
            "replenish_no",
            "replenish_date",
            "amount",
            "reference",
            "status",
            "journal_entry",
        ]
        read_only_fields = ["replenish_no", "status", "journal_entry"]


class DenominationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Denomination
        fields = ["id", "denomination_value", "quantity", "amount"]
        read_only_fields = ["amount"]


class CashCountSerializer(serializers.ModelSerializer):
    """A draft names entity/cash_account/count_date (+ optional counted_by/
    variance_account) plus its denomination tally; `post` recomputes
    counted_amount/variance from those lines and books any variance."""

    denominations = DenominationSerializer(many=True)

    class Meta:
        model = CashCount
        fields = [
            "id",
            "entity",
            "cash_account",
            "count_no",
            "count_date",
            "counted_by",
            "expected_amount",
            "counted_amount",
            "variance",
            "variance_account",
            "status",
            "journal_entry",
            "denominations",
        ]
        read_only_fields = ["count_no", "counted_amount", "variance", "status", "journal_entry"]

    def create(self, validated_data):
        denominations = validated_data.pop("denominations", [])
        count = CashCount.objects.create(**validated_data)
        for row in denominations:
            Denomination.objects.create(cash_count=count, **row)
        return count
