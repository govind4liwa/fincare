"""DRF serializers for per-entity configuration."""

from rest_framework import serializers

from apps.settings.models import DriverAccountingConfig
from apps.settings.services.driver_accounting import (
    DriverAccountingConfigError,
    set_driver_receivable_account,
    validate_receivable_account,
)


class DriverAccountingConfigSerializer(serializers.ModelSerializer):
    account_code = serializers.CharField(source="default_receivable_account.code", read_only=True)
    account_name = serializers.CharField(source="default_receivable_account.name", read_only=True)

    class Meta:
        model = DriverAccountingConfig
        fields = [
            "id",
            "entity",
            "default_receivable_account",
            "account_code",
            "account_name",
        ]

    def validate(self, attrs):
        entity = attrs.get("entity") or getattr(self.instance, "entity", None)
        account = attrs.get("default_receivable_account") or getattr(
            self.instance, "default_receivable_account", None
        )
        # Mirrors the service gate so the API returns a field-level error; the
        # service remains the authority (save() never calls full_clean()).
        try:
            validate_receivable_account(entity, account)
        except DriverAccountingConfigError as exc:
            raise serializers.ValidationError({"default_receivable_account": str(exc)}) from exc
        return attrs

    # Writes go through the service rather than the default ModelSerializer
    # behaviour, so the API cannot diverge from it. In particular the service
    # revives a soft-deleted configuration; `objects.create()` would instead
    # collide with the unique key that hidden row still holds.
    def create(self, validated_data):
        return set_driver_receivable_account(
            validated_data["entity"], validated_data["default_receivable_account"]
        )

    def update(self, instance, validated_data):
        return set_driver_receivable_account(
            validated_data.get("entity", instance.entity),
            validated_data.get("default_receivable_account", instance.default_receivable_account),
        )
