"""DRF serializer for the append-only audit trail — read-only by design,
since rows are written exclusively by apps.audit.services.record."""

from rest_framework import serializers

from apps.audit.models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    actor_email = serializers.CharField(source="actor.email", read_only=True, default=None)
    content_type_label = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "timestamp",
            "actor",
            "actor_email",
            "action",
            "content_type_label",
            "object_id",
            "object_repr",
            "entity_id",
            "changes",
            "message",
        ]
        read_only_fields = fields

    def get_content_type_label(self, obj):
        if obj.content_type_id is None:
            return None
        return f"{obj.content_type.app_label}.{obj.content_type.model}"
