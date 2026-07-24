"""Append-only audit trail (design doc, CLAUDE.md §11).

An ``AuditLog`` row is written explicitly from the service layer (see
``apps.audit.services.record``) whenever a meaningful action occurs — create,
update, post, reverse, etc. The log is **append-only**: rows cannot be updated or
deleted through the ORM (enforced in ``save``/``delete``; a DB trigger can be
added later for defence in depth).

It is intentionally standalone (not ``BaseModel``) — no soft delete, no
``updated_*`` — because an audit record is immutable by definition.
"""

import uuid

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class AuditLog(models.Model):
    class Action(models.TextChoices):
        CREATE = "create", "Create"
        UPDATE = "update", "Update"
        DELETE = "delete", "Delete"
        POST = "post", "Post"
        REVERSE = "reverse", "Reverse"
        CANCEL = "cancel", "Cancel"
        LOGIN = "login", "Login"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    action = models.CharField(max_length=12, choices=Action.choices, db_index=True)
    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True)
    object_id = models.CharField(max_length=64, blank=True, db_index=True)
    content_object = GenericForeignKey("content_type", "object_id")
    object_repr = models.CharField(max_length=255, blank=True)
    entity_id = models.UUIDField(null=True, blank=True, db_index=True)
    changes = models.JSONField(default=dict, blank=True)  # {field: [old, new]}
    message = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
            models.Index(fields=["entity_id", "-timestamp"]),
        ]

    def __str__(self):
        return f"{self.action} {self.object_repr} @ {self.timestamp:%Y-%m-%d %H:%M}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("AuditLog is append-only; existing rows cannot be modified.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("AuditLog is append-only; rows cannot be deleted.")
