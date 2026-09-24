"""Seed the outstanding receivable on settlements posted before clearing existed.

A negative-net settlement has always debited the Driver Receivable account, but
until now nothing tracked how much of it was still owed. Without this, every
historical shortfall would read as fully settled and could never be cleared.

Deterministic and idempotent: only posted settlements with a negative net and no
clearing activity yet are touched, and the balance is derived from the amount
already posted rather than recomputed from deductions.
"""

from django.db import migrations


def backfill(apps, schema_editor):
    Settlement = apps.get_model("drivers", "Settlement")
    # `status` is a plain CharField on the historical model; "posted" is the value
    # DriverDocStatus.POSTED carries and is stable in the DB.
    outstanding = Settlement.objects.filter(
        status="posted",
        net_amount__lt=0,
        cleared_amount=0,
        receivable_balance=0,
    )
    for settlement in outstanding.iterator():
        settlement.receivable_balance = -settlement.net_amount
        settlement.save(update_fields=["receivable_balance"])


def unbackfill(apps, schema_editor):
    """Reverse only rows this migration could have created: nothing cleared yet."""
    Settlement = apps.get_model("drivers", "Settlement")
    Settlement.objects.filter(status="posted", net_amount__lt=0, cleared_amount=0).update(
        receivable_balance=0
    )


class Migration(migrations.Migration):
    dependencies = [
        ("drivers", "0005_settlement_cleared_amount_and_more"),
    ]

    operations = [migrations.RunPython(backfill, unbackfill)]
