"""DRF serializers for AR customers."""

from rest_framework import serializers

from apps.ar.models import Customer


class CustomerSerializer(serializers.ModelSerializer):
    receivable_account_code = serializers.CharField(
        source="receivable_account.code", read_only=True
    )

    class Meta:
        model = Customer
        fields = [
            "id",
            "entity",
            "code",
            "name",
            "trn",
            "customer_type",
            "receivable_account",
            "receivable_account_code",
            "currency",
            "credit_limit",
            "credit_days",
            "email",
            "phone",
            "address",
            "emirate",
            "opening_balance",
            "is_active",
        ]
