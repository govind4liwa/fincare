"""Audit capture service.

Domain code calls ``record(...)`` explicitly (from the service layer) rather than
relying on global signals, so the audit trail is precise and intentional —
especially for accounting postings. A ``snapshot``/``diff`` pair helps build the
``changes`` payload for updates.
"""

from django.contrib.contenttypes.models import ContentType
from django.forms.models import model_to_dict

from apps.audit.models import AuditLog


def snapshot(instance, fields=None):
    """A plain-dict snapshot of an instance's field values (for diffing)."""
    data = model_to_dict(instance, fields=fields)
    # JSON-safe: stringify non-serialisable values (UUID, Decimal, dates, FKs).
    return {
        k: (v if isinstance(v, str | int | float | bool | type(None)) else str(v))
        for k, v in data.items()
    }


def diff(before: dict, after: dict) -> dict:
    """Return ``{field: [old, new]}`` for fields that changed."""
    changed = {}
    for key in set(before) | set(after):
        old, new = before.get(key), after.get(key)
        if old != new:
            changed[key] = [old, new]
    return changed


def _resolve_entity_id(instance, entity_id):
    if entity_id is not None:
        return entity_id
    return getattr(instance, "entity_id", None)


def record(
    *,
    action,
    instance=None,
    actor=None,
    entity_id=None,
    changes=None,
    content_type=None,
    object_id=None,
    object_repr=None,
    message="",
):
    """Write one append-only audit row. Returns the created AuditLog."""
    if instance is not None:
        content_type = content_type or ContentType.objects.get_for_model(instance)
        object_id = object_id if object_id is not None else str(instance.pk)
        object_repr = object_repr if object_repr is not None else str(instance)[:255]

    return AuditLog.objects.create(
        action=action,
        actor=actor,
        content_type=content_type,
        object_id=object_id or "",
        object_repr=object_repr or "",
        entity_id=_resolve_entity_id(instance, entity_id),
        changes=changes or {},
        message=message,
    )
