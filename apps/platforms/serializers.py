"""DRF serializers for platform master data, settlements, and staged earnings."""

from rest_framework import serializers

from apps.platforms.models import EarningImport, Platform, PlatformSettlement


class PlatformSerializer(serializers.ModelSerializer):
    revenue_account_code = serializers.CharField(source="revenue_account.code", read_only=True)
    commission_account_code = serializers.CharField(
        source="commission_account.code", read_only=True
    )
    clearing_account_code = serializers.CharField(source="clearing_account.code", read_only=True)

    class Meta:
        model = Platform
        fields = [
            "id",
            "entity",
            "name",
            "commission_pct",
            "settlement_cycle",
            "revenue_account",
            "revenue_account_code",
            "commission_account",
            "commission_account_code",
            "clearing_account",
            "clearing_account_code",
            "is_active",
        ]


class EarningImportSerializer(serializers.ModelSerializer):
    platform_name = serializers.CharField(source="platform.name", read_only=True)

    class Meta:
        model = EarningImport
        fields = [
            "id",
            "entity",
            "platform",
            "platform_name",
            "settlement",
            "trip_ref",
            "driver_ref",
            "earning_date",
            "gross",
            "commission",
            "net",
            "matched",
        ]
        # A settlement claims rows via `reconcile`; matched follows automatically.
        # Manual entry today — a future integrations importer populates these in
        # bulk without changing this shape.
        read_only_fields = ["settlement", "matched"]


class PlatformSettlementSerializer(serializers.ModelSerializer):
    """A draft names its platform/period/net_received; `reconcile` aggregates
    gross/commission from staged EarningImport rows and computes variance;
    `post` books the entry. Those derived fields are read-only here."""

    platform_name = serializers.CharField(source="platform.name", read_only=True)

    class Meta:
        model = PlatformSettlement
        fields = [
            "id",
            "entity",
            "platform",
            "platform_name",
            "settlement_no",
            "period_start",
            "period_end",
            "settlement_date",
            "gross_earnings",
            "commission",
            "adjustments",
            "net_received",
            "variance",
            "bank_account",
            "adjustment_account",
            "status",
            "journal_entry",
        ]
        read_only_fields = [
            "settlement_no",
            "gross_earnings",
            "commission",
            "variance",
            "status",
            "journal_entry",
        ]
