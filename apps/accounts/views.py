"""Chart of Accounts API — groups, accounts, tax codes (entity-scoped, read-only).

Like the tenants API, results are scoped to the requesting user's accessible
entities in the queryset so it's correct even with RLS off; a superuser sees all.
The frontend narrows to the selected entity via the `?entity=<id>` filter.
"""

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps.accounts.models import Account, AccountGroup, TaxCode
from apps.accounts.serializers import (
    AccountGroupSerializer,
    AccountSerializer,
    TaxCodeSerializer,
)
from apps.tenants.views import accessible_entity_ids


def scope_to_entities(queryset, user, field="entity_id"):
    """Restrict ``queryset`` to the entities ``user`` may access (superuser = all)."""
    ids = accessible_entity_ids(user)
    return queryset if ids is None else queryset.filter(**{f"{field}__in": ids})


class AccountGroupViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AccountGroupSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["entity", "level", "nature", "parent", "is_active"]
    ordering_fields = ["code", "name"]
    ordering = ["code"]

    def get_queryset(self):
        return scope_to_entities(AccountGroup.objects.select_related("parent"), self.request.user)


class AccountViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AccountSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["entity", "account_type", "sub_group", "is_active", "is_postable"]
    ordering_fields = ["code", "name"]
    ordering = ["code"]

    def get_queryset(self):
        return scope_to_entities(Account.objects.select_related("sub_group"), self.request.user)


class TaxCodeViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = TaxCodeSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["entity", "treatment", "direction", "is_active"]
    ordering_fields = ["code"]
    ordering = ["code"]

    def get_queryset(self):
        return scope_to_entities(TaxCode.objects.select_related("account"), self.request.user)
