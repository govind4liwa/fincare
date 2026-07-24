"""DRF serializers for the Chart of Accounts (groups, accounts, tax codes)."""

from rest_framework import serializers

from apps.accounts.models import Account, AccountGroup, TaxCode


class AccountGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccountGroup
        fields = [
            "id",
            "entity",
            "level",
            "segment",
            "parent",
            "code",
            "name",
            "nature",
            "is_active",
        ]


class AccountSerializer(serializers.ModelSerializer):
    account_type_display = serializers.CharField(source="get_account_type_display", read_only=True)
    sub_group_code = serializers.CharField(source="sub_group.code", read_only=True)
    sub_group_name = serializers.CharField(source="sub_group.name", read_only=True)
    # An account's nature is inherited from its (sub) group.
    nature = serializers.CharField(source="sub_group.nature", read_only=True)

    class Meta:
        model = Account
        fields = [
            "id",
            "entity",
            "sub_group",
            "sub_group_code",
            "sub_group_name",
            "nature",
            "charge_segment",
            "code",
            "name",
            "account_type",
            "account_type_display",
            "normal_balance",
            "currency",
            "is_control_account",
            "subledger",
            "is_bank_account",
            "allow_manual_posting",
            "is_postable",
            "is_active",
        ]


class TaxCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaxCode
        fields = [
            "id",
            "entity",
            "code",
            "name",
            "rate",
            "treatment",
            "direction",
            "account",
            "is_active",
        ]
