"""Tenancy API: entities & branches, scoped to the requesting user's memberships.

Scoping is enforced here in the queryset (not only via RLS) because
``RLS_ENABLED`` is off by default — the API must be correct either way. A
superuser sees everything; everyone else sees only entities they hold an active
``UserEntityMembership`` for. This mirrors the middleware's RLS logic.
"""

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps.tenants.models import Branch, Entity, UserEntityMembership
from apps.tenants.serializers import BranchSerializer, EntitySerializer


def accessible_entity_ids(user):
    """Entity ids the user may access; ``None`` means unrestricted (superuser)."""
    if user.is_superuser:
        return None
    return list(
        UserEntityMembership.objects.filter(user=user, is_active=True).values_list(
            "entity_id", flat=True
        )
    )


class EntityViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = EntitySerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["category", "accounting_basis", "is_active"]
    ordering_fields = ["numeric_code", "legal_name"]
    ordering = ["numeric_code"]

    def get_queryset(self):
        qs = Entity.objects.select_related("category", "vat_group", "base_currency")
        ids = accessible_entity_ids(self.request.user)
        return qs if ids is None else qs.filter(id__in=ids)


class BranchViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = BranchSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["entity", "is_active"]
    ordering = ["entity", "code"]

    def get_queryset(self):
        qs = Branch.objects.select_related("entity")
        ids = accessible_entity_ids(self.request.user)
        return qs if ids is None else qs.filter(entity_id__in=ids)
