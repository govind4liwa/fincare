"""DRF serializers for the Chart of Accounts (groups, accounts, tax codes)."""

import logging
import re

from rest_framework import serializers

from apps.accounts.models import Account, AccountGroup, TaxCode
from apps.accounts.services import authoring

logger = logging.getLogger(__name__)


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


class AccountWriteSerializer(serializers.ModelSerializer):
    """Create/edit a postable account. The code is composed by the service from
    the Sub group + charge segment (ADR-0004) and is immutable once created."""

    # Derived server-side, never trusted from input.
    normal_balance = serializers.CharField(required=False, allow_blank=True, max_length=1)
    code = serializers.CharField(read_only=True)
    sub_group_code = serializers.CharField(source="sub_group.code", read_only=True)
    nature = serializers.CharField(source="sub_group.nature", read_only=True)

    class Meta:
        model = Account
        fields = [
            "id",
            "entity",
            "sub_group",
            "sub_group_code",
            "nature",
            "charge_segment",
            "code",
            "name",
            "account_type",
            "normal_balance",
            "currency",
            "is_control_account",
            "subledger",
            "is_bank_account",
            "allow_manual_posting",
            "is_postable",
            "is_active",
        ]
        read_only_fields = ["code"]

    def validate_charge_segment(self, value):
        if not re.fullmatch(r"\d{3}", value or ""):
            raise serializers.ValidationError("Charge segment must be exactly 3 digits (e.g. 004).")
        return value

    def create(self, validated_data):
        try:
            return authoring.create_account(
                entity=validated_data["entity"],
                sub_group=validated_data["sub_group"],
                charge_segment=validated_data["charge_segment"],
                name=validated_data["name"],
                account_type=validated_data["account_type"],
                normal_balance=validated_data.get("normal_balance", ""),
                currency=validated_data.get("currency"),
                is_control_account=validated_data.get("is_control_account", False),
                subledger=validated_data.get("subledger", ""),
                is_bank_account=validated_data.get("is_bank_account", False),
                allow_manual_posting=validated_data.get("allow_manual_posting", True),
                is_postable=validated_data.get("is_postable", True),
                is_active=validated_data.get("is_active", True),
            )
        except authoring.AccountError as exc:
            # Log the detail server-side; return a safe, non-leaking message.
            logger.warning("Account creation rejected: %s", exc)
            raise serializers.ValidationError(
                {
                    "non_field_errors": [
                        "Could not create the account — it may already exist, or the "
                        "sub-group / charge segment is invalid."
                    ]
                }
            ) from exc

    def update(self, instance, validated_data):
        # ADR-0004: an account's code is immutable. The Sub group and charge
        # segment (which compose the code) cannot change; corrections = a new account.
        immutable_changed = (
            "sub_group" in validated_data
            and validated_data["sub_group"].pk != instance.sub_group_id
        ) or (
            "charge_segment" in validated_data
            and validated_data["charge_segment"] != instance.charge_segment
        )
        if immutable_changed:
            raise serializers.ValidationError(
                {
                    "non_field_errors": [
                        "An account's code is immutable; create a new account instead."
                    ]
                }
            )
        for locked in ("entity", "sub_group", "charge_segment"):
            validated_data.pop(locked, None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


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
