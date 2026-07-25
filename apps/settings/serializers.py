"""DRF serializers for per-entity configuration."""

from rest_framework import serializers

from apps.settings.models import DriverAccountingConfig
from apps.settings.services.driver_accounting import (
    receivable_account_error,
    set_driver_receivable_account,
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
        # The service owns the rules; this asks it for the reason as data rather
        # than catching its exception, so no exception text reaches the response.
        problem = receivable_account_error(entity, account)
        if problem is not None:
            raise serializers.ValidationError({"default_receivable_account": problem})
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
