"""DRF serializers for ledger resources (accounting periods)."""

import logging

from rest_framework import serializers

from apps.ledger.models import AccountingPeriod
from apps.ledger.services import periods

logger = logging.getLogger(__name__)


class AccountingPeriodSerializer(serializers.ModelSerializer):
    """A period is created OPEN, naming entity/fiscal_year/period_no/dates;
    every later change (close/reopen/lock) goes through a named transition
    action, never a direct field edit — status/closed_at/closed_by are
    read-only here, and `create` delegates to the periods service so overlap
    validation can't be bypassed by writing straight to the model."""

    closed_by_email = serializers.EmailField(source="closed_by.email", read_only=True)

    class Meta:
        model = AccountingPeriod
        fields = [
            "id",
            "entity",
            "fiscal_year",
            "period_no",
            "name",
            "start_date",
            "end_date",
            "status",
            "closed_at",
            "closed_by_email",
        ]
        read_only_fields = ["status", "closed_at"]

    def create(self, validated_data):
        try:
            return periods.create_period(
                validated_data["entity"],
                fiscal_year=validated_data["fiscal_year"],
                period_no=validated_data["period_no"],
                name=validated_data["name"],
                start_date=validated_data["start_date"],
                end_date=validated_data["end_date"],
                user=self.context["request"].user,
            )
        except periods.PeriodError as exc:
            logger.warning("Period creation rejected: %s", exc)
            raise serializers.ValidationError(
                {
                    "non_field_errors": [
                        "Could not create this period — check the dates don't overlap an "
                        "existing period, start is on or before end, and the fiscal year/"
                        "period number combination isn't already used."
                    ]
                }
            ) from exc
