"""Tenant-context middleware enforcing RLS per request (ADR-0008).

Gated by ``settings.RLS_ENABLED`` (default False) so it can be rolled out
deliberately. When enabled, each request runs inside a transaction with:
- ``SET LOCAL ROLE`` to the restricted app role (so RLS actually applies — the
  pooled connection logs in as a privileged role used for migrations/admin), and
- ``app.current_entities`` set to the comma-separated entity ids the user may
  access (via ``set_config(..., true)`` = transaction-local).

``SET LOCAL`` / transaction-local config never leak across requests. Superusers
get the sentinel (GUC left unset) that the RLS policy treats as unrestricted.

User resolution handles both session auth (admin) and JWT (DRF API), since DRF
resolves the JWT user in the view layer — after this middleware — so we attempt
JWT authentication here explicitly.
"""

from django.conf import settings
from django.db import connection, transaction

GUC = "app.current_entities"


def _resolve_user(request):
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        return user
    # DRF/JWT: the bearer token isn't resolved until the view; do it here.
    from rest_framework_simplejwt.authentication import JWTAuthentication

    try:
        result = JWTAuthentication().authenticate(request)
    except Exception:  # auth failures => treat as anonymous
        result = None
    return result[0] if result is not None else None


def _allowed_entity_ids(user):
    """Active entity ids the user may access; None = unrestricted (superuser)."""
    if user is None or not user.is_authenticated:
        return []
    if user.is_superuser:
        return None
    from apps.tenants.models import UserEntityMembership

    return [
        str(eid)
        for eid in UserEntityMembership.objects.filter(user=user, is_active=True).values_list(
            "entity_id", flat=True
        )
    ]


class TenantContextMiddleware:
    """Sets the per-request DB role + entity context for RLS (when enabled)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not getattr(settings, "RLS_ENABLED", False):
            return self.get_response(request)

        role = getattr(settings, "RLS_APP_ROLE", "fincare_app")
        entity_ids = _allowed_entity_ids(_resolve_user(request))
        request.allowed_entity_ids = entity_ids
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(f'SET LOCAL ROLE "{role}"')
            if entity_ids is not None:
                cursor.execute("SELECT set_config(%s, %s, true)", [GUC, ",".join(entity_ids)])
            return self.get_response(request)
