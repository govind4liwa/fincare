"""Configure each existing entity's Driver Receivable account.

Points every entity at its own seeded ``Staff Advances`` account, identified by
entity-independent characteristics rather than any full code (``EEE-100-120-003``
differs per entity). Deterministic and idempotent: entities already configured
are skipped, and an entity without exactly one unambiguous match is deliberately
left unconfigured rather than pointed at some other asset account — it simply
cannot post a negative-net settlement until someone configures it.

No account classification is changed by this migration.
"""

from django.db import migrations

# Kept literal rather than imported: migrations must not drift with the service.
STAFF_ADVANCE_MARKERS = {
    "sub_group__segment": "120",
    "charge_segment": "003",
    "name": "Staff Advances",
    "account_type": "general",
    "is_control_account": False,
    "subledger": "",
    "sub_group__nature": "asset",
    "is_active": True,
    "is_postable": True,
    "normal_balance": "D",
    "is_bank_account": False,
}


def backfill(apps, schema_editor):
    Entity = apps.get_model("tenants", "Entity")
    Account = apps.get_model("accounts", "Account")
    Config = apps.get_model("settings", "DriverAccountingConfig")

    configured = set(Config.objects.values_list("entity_id", flat=True))
    for entity in Entity.objects.all():
        if entity.id in configured:
            continue  # idempotent: never re-point an existing configuration
        matches = list(Account.objects.filter(entity=entity, **STAFF_ADVANCE_MARKERS)[:2])
        if len(matches) != 1:
            continue  # ambiguous or absent — leave unconfigured, never guess
        Config.objects.create(entity=entity, default_receivable_account=matches[0])


def unbackfill(apps, schema_editor):
    """Reverse by removing only rows this migration could have created."""
    Config = apps.get_model("settings", "DriverAccountingConfig")
    Config.objects.filter(
        default_receivable_account__name="Staff Advances",
        default_receivable_account__charge_segment="003",
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("settings", "0003_driveraccountingconfig"),
        ("accounts", "0001_initial"),
        ("tenants", "0001_initial"),
    ]

    operations = [migrations.RunPython(backfill, unbackfill)]
