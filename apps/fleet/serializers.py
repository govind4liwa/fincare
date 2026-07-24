"""DRF serializers for fleet vehicles."""

from rest_framework import serializers

from apps.fleet.models import Vehicle


class VehicleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = [
            "id",
            "entity",
            "code",
            "plate_no",
            "plate_emirate",
            "make",
            "model",
            "model_year",
            "vin",
            "ownership",
            "acquisition_date",
            "acquisition_cost",
            "is_active",
        ]
