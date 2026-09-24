"""DRF serializers for the trip register and corporate contracts."""

from rest_framework import serializers

from apps.bookings.models import Contract, Trip


class TripSerializer(serializers.ModelSerializer):
    vehicle_code = serializers.CharField(source="vehicle.code", read_only=True)
    driver_code = serializers.CharField(source="driver.code", read_only=True)
    platform_name = serializers.CharField(source="platform.name", read_only=True)
    customer_name = serializers.CharField(source="customer.name", read_only=True)

    class Meta:
        model = Trip
        fields = [
            "id",
            "entity",
            "trip_date",
            "trip_type",
            "vehicle",
            "vehicle_code",
            "driver",
            "driver_code",
            "platform",
            "platform_name",
            "customer",
            "customer_name",
            "fare",
            "commission",
            "salik",
            "tip",
            "distance_km",
            "net_revenue",
            "status",
            "revenue_journal_entry",
        ]
        # Revenue recognition is a periodic aggregate posting (post_aggregate_revenue),
        # never a per-trip edit — these are derived at post time.
        read_only_fields = ["net_revenue", "status", "revenue_journal_entry"]


class ContractSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    vehicle_code = serializers.CharField(source="vehicle.code", read_only=True)
    driver_code = serializers.CharField(source="driver.code", read_only=True)
    revenue_account_code = serializers.CharField(source="revenue_account.code", read_only=True)
    tax_code_code = serializers.CharField(source="tax_code.code", read_only=True)

    class Meta:
        model = Contract
        fields = [
            "id",
            "entity",
            "customer",
            "customer_name",
            "vehicle",
            "vehicle_code",
            "driver",
            "driver_code",
            "contract_no",
            "start_date",
            "end_date",
            "billing_cycle",
            "monthly_amount",
            "revenue_account",
            "revenue_account_code",
            "tax_code",
            "tax_code_code",
            "status",
        ]
