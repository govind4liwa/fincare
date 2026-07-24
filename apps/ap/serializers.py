"""DRF serializers for AP suppliers."""

from rest_framework import serializers

from apps.ap.models import Supplier


class SupplierSerializer(serializers.ModelSerializer):
    payable_account_code = serializers.CharField(source="payable_account.code", read_only=True)

    class Meta:
        model = Supplier
        fields = [
            "id",
            "entity",
            "code",
            "name",
            "trn",
            "payable_account",
            "payable_account_code",
            "currency",
            "credit_days",
            "email",
            "phone",
            "address",
            "opening_balance",
            "is_active",
        ]
