"""Gap-safe document number allocation.

Concurrency model: the counter row is locked with ``SELECT ... FOR UPDATE``
inside an atomic block, so concurrent callers serialise on that row and can
never receive the same number. Allocation is gap-safe (no skipped numbers)
because the increment commits with the surrounding transaction.
"""

from dataclasses import dataclass

from django.db import transaction

from apps.core.models import NumberSequence


@dataclass(frozen=True)
class AllocatedNumber:
    value: int  # raw sequential integer (e.g. 1, 2, 3)
    formatted: str  # rendered document number (e.g. "INV-000001")


def ensure_sequence(
    *,
    entity_id,
    code,
    period_key="",
    prefix="",
    suffix="",
    padding=6,
    reset_policy=NumberSequence.ResetPolicy.NEVER,
):
    """Idempotently create the counter row for a scope; return it."""
    seq, _ = NumberSequence.all_objects.get_or_create(
        entity_id=entity_id,
        code=code,
        period_key=period_key,
        defaults={
            "prefix": prefix,
            "suffix": suffix,
            "padding": padding,
            "next_value": 1,
            "reset_policy": reset_policy,
        },
    )
    return seq


def allocate(*, entity_id, code, period_key="", **defaults):
    """Allocate the next number for (entity, code, period_key).

    Must be called inside (or will open) a DB transaction; the returned number
    is committed atomically with the caller's posting when wrapped together.
    """
    # Ensure the row exists before we try to lock it.
    ensure_sequence(entity_id=entity_id, code=code, period_key=period_key, **defaults)

    with transaction.atomic():
        seq = NumberSequence.all_objects.select_for_update().get(
            entity_id=entity_id, code=code, period_key=period_key
        )
        value = seq.next_value
        seq.next_value = value + 1
        seq.save(update_fields=["next_value", "updated_at"])

    return AllocatedNumber(value=value, formatted=seq.format(value))
