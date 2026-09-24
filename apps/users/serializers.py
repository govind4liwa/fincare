"""DRF serializer for the current user's own profile.

Not a user-management API — creation/role assignment stay in Django admin
for now. This exists to give the frontend a real permission surface (see
`lib/nav-config.ts`'s `filterNavByAccess`, currently unwired for lack of
exactly this).
"""

from rest_framework import serializers

from apps.tenants.views import accessible_entity_ids
from apps.users.models import User


class MeSerializer(serializers.ModelSerializer):
    roles = serializers.SerializerMethodField()
    entities = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "email", "full_name", "is_staff", "is_superuser", "roles", "entities"]
        read_only_fields = fields

    def get_roles(self, obj):
        return list(obj.groups.values_list("name", flat=True))

    def get_entities(self, obj):
        """Accessible entity ids, or ``None`` meaning unrestricted (superuser)."""
        ids = accessible_entity_ids(obj)
        return None if ids is None else [str(entity_id) for entity_id in ids]
