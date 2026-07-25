"""DRF serializers for drivers, advances, and settlements."""

from rest_framework import serializers

from apps.drivers.models import Advance, Driver, Settlement, SettlementDeduction


class DriverSerializer(serializers.ModelSerializer):
    class Meta:
        model = Driver
        fields = [
            "id",
            "entity",
            "code",
            "name",
            "nationality",
            "licence_no",
            "emirates_id",
            "phone",
            "basic_salary",
            "commission_rate",
            "is_active",
        ]


class AdvanceSerializer(serializers.ModelSerializer):
    driver_code = serializers.CharField(source="driver.code", read_only=True)
    driver_name = serializers.CharField(source="driver.name", read_only=True)

    class Meta:
        model = Advance
        fields = [
            "id",
            "entity",
            "driver",
            "driver_code",
            "driver_name",
            "advance_no",
            "advance_date",
            "amount",
            "recovered_amount",
            "balance",
            "advance_account",
            "bank_account",
            "status",
            "journal_entry",
        ]
        # Numbering, recovery progress, and status are owned by the posting service.
        read_only_fields = [
            "advance_no",
            "recovered_amount",
            "balance",
            "status",
            "journal_entry",
        ]

    def validate(self, attrs):
        entity = attrs.get("entity") or getattr(self.instance, "entity", None)
        driver = attrs.get("driver") or getattr(self.instance, "driver", None)
        if entity is not None and driver is not None and driver.entity_id != entity.id:
            raise serializers.ValidationError({"driver": "Driver belongs to a different entity."})
        if attrs.get("amount") is not None and attrs["amount"] <= 0:
            raise serializers.ValidationError({"amount": "Advance amount must be positive."})
        return attrs


class SettlementDeductionSerializer(serializers.ModelSerializer):
    kind_display = serializers.CharField(source="get_kind_display", read_only=True)

    class Meta:
        model = SettlementDeduction
        fields = ["id", "kind", "account", "amount", "advance", "description", "kind_display"]


class SettlementSerializer(serializers.ModelSerializer):
    deductions = SettlementDeductionSerializer(many=True)
    driver_code = serializers.CharField(source="driver.code", read_only=True)
    driver_name = serializers.CharField(source="driver.name", read_only=True)

    class Meta:
        model = Settlement
        fields = [
            "id",
            "entity",
            "driver",
            "driver_code",
            "driver_name",
            "vehicle",
            "settlement_no",
            "period_start",
            "period_end",
            "settlement_date",
            "gross_amount",
            "gross_account",
            "pay_account",
            "total_deductions",
            "net_amount",
            "allows_negative_net",
            "status",
            "journal_entry",
            "deductions",
        ]
        # Totals, numbering, and status are derived when the settlement posts.
        read_only_fields = [
            "settlement_no",
            "total_deductions",
            "net_amount",
            "status",
            "journal_entry",
        ]

    def validate(self, attrs):
        entity = attrs.get("entity") or getattr(self.instance, "entity", None)
        driver = attrs.get("driver") or getattr(self.instance, "driver", None)
        if entity is not None and driver is not None and driver.entity_id != entity.id:
            raise serializers.ValidationError({"driver": "Driver belongs to a different entity."})
        start, end = attrs.get("period_start"), attrs.get("period_end")
        if start and end and end < start:
            raise serializers.ValidationError(
                {"period_end": "Period end cannot precede period start."}
            )
        if attrs.get("gross_amount") is not None and attrs["gross_amount"] <= 0:
            raise serializers.ValidationError({"gross_amount": "Gross amount must be positive."})
        return attrs

    def create(self, validated_data):
        deductions = validated_data.pop("deductions", [])
        settlement = Settlement.objects.create(**validated_data)
        for line in deductions:
            SettlementDeduction.objects.create(settlement=settlement, **line)
        return settlement
