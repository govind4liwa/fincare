"""Audit API: read-only access to the append-only AuditLog.

Restricted to accountant/manager/admin (not every member) since the trail
covers other users' actions across the entity, not just the caller's own.
"""

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps.audit.models import AuditLog
from apps.audit.serializers import AuditLogSerializer
from apps.tenants.views import accessible_entity_ids
from apps.users.permissions import HasAnyRole

ROLES = ("accountant", "manager", "admin")


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated, HasAnyRole]
    required_roles = ROLES
    filterset_fields = ["entity_id", "action", "content_type"]
    ordering_fields = ["timestamp"]
    ordering = ["-timestamp"]

    def get_queryset(self):
        qs = AuditLog.objects.select_related("actor", "content_type")
        ids = accessible_entity_ids(self.request.user)
        if ids is None:
            return qs
        # Cross-entity/system rows (entity_id is null — e.g. currency seeding)
        # aren't part of any single entity's trail, so they stay superuser-only.
        return qs.filter(entity_id__in=ids)
