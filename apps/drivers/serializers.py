"""DRF serializers for drivers."""

from rest_framework import serializers

from apps.drivers.models import Driver


class DriverSerializer(serializers.ModelSerializer):
    class Meta:
        model = Driver
        fields = [
            "id",
            "entity",
            "code",
            "name",
            "nationality",
            "licence_no",
            "emirates_id",
            "phone",
            "basic_salary",
            "commission_rate",
            "is_active",
        ]
