"""Reusable DRF permission classes for role-based access control.

Roles are modelled as Django Groups (``user.groups``). Two layers are available:
- ``HasAnyRole`` — declarative group check via a ``required_roles`` attr on the
  view (e.g. ``required_roles = ("accountant", "manager")``).
- Django's built-in model permissions (via ``DjangoModelPermissions``) remain
  available for object/CRUD-level control on ViewSets.
"""

from rest_framework.permissions import BasePermission


class HasAnyRole(BasePermission):
    """Allow authenticated users who belong to any of the view's required roles.

    If the view declares no ``required_roles``, this degrades to
    "must be authenticated".
    """

    message = "You do not have the required role for this action."

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        required = tuple(getattr(view, "required_roles", ()) or ())
        if not required:
            return True
        if user.is_superuser:
            return True
        return user.groups.filter(name__in=required).exists()
