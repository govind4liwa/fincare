"""Idempotent Chart-of-Accounts seeding from category templates (ADR-0005).

``seed_entity_coa(entity)`` walks the entity's category template and creates the
Main/Sub groups and Charge-code accounts, composing codes via ``coding``. Safe to
re-run: existing rows are left untouched (additive only).
"""

from django.db import transaction

from apps.accounts.models import Account, AccountGroup, TaxCode
from apps.accounts.services import coding, templates

# Default UAE VAT codes seeded per entity (rates are config; confirm with advisor).
VAT_DEFAULTS = [
    ("SR", "Standard Rated 5%", "5.000", TaxCode.Treatment.STANDARD),
    ("ZR", "Zero Rated", "0", TaxCode.Treatment.ZERO),
    ("EX", "Exempt", "0", TaxCode.Treatment.EXEMPT),
    ("OS", "Out of Scope", "0", TaxCode.Treatment.OUT_OF_SCOPE),
    ("RC", "Reverse Charge", "5.000", TaxCode.Treatment.REVERSE_CHARGE),
    ("NA", "Not Applicable", "0", TaxCode.Treatment.OUT_OF_SCOPE),
]


def seed_tax_codes(entity):
    created = 0
    for code, name, rate, treatment in VAT_DEFAULTS:
        _, was_created = TaxCode.objects.get_or_create(
            entity=entity,
            code=code,
            defaults={"name": name, "rate": rate, "treatment": treatment},
        )
        created += int(was_created)
    return created


@transaction.atomic
def seed_entity_coa(entity):
    """Create the entity's COA from its category template. Idempotent."""
    category_key = entity.category.key
    expected_band = templates.BANDS.get(category_key)
    if expected_band is not None and entity.numeric_code[:1] != expected_band:
        raise ValueError(
            f"entity {entity.numeric_code} band does not match category "
            f"{category_key!r} (expected band {expected_band})"
        )

    entity_code = entity.numeric_code
    rows = templates.account_rows(category_key)
    main_groups = {}
    sub_groups = {}
    groups_created = 0
    accounts_created = 0

    for row in rows:
        main, sub, charge = row["main"], row["sub"], row["charge"]

        if main not in main_groups:
            group, was_created = AccountGroup.objects.get_or_create(
                entity=entity,
                level=1,
                segment=main,
                parent=None,
                defaults={
                    "code": coding.compose_group_code(entity_code, main),
                    "name": row["main_name"],
                    "nature": coding.nature_for_main(main),
                },
            )
            main_groups[main] = group
            groups_created += int(was_created)
        main_group = main_groups[main]

        sub_key = (main, sub)
        if sub_key not in sub_groups:
            group, was_created = AccountGroup.objects.get_or_create(
                entity=entity,
                level=2,
                segment=sub,
                parent=main_group,
                defaults={
                    "code": coding.compose_group_code(entity_code, main, sub),
                    "name": row["sub_name"],
                    "nature": coding.nature_for_main(main),
                },
            )
            sub_groups[sub_key] = group
            groups_created += int(was_created)
        sub_group = sub_groups[sub_key]

        is_control = row["control"]
        _, was_created = Account.objects.get_or_create(
            entity=entity,
            sub_group=sub_group,
            charge_segment=charge,
            defaults={
                "code": coding.compose_account_code(entity_code, main, sub, charge),
                "name": row["name"],
                "account_type": row["account_type"],
                "normal_balance": coding.normal_balance_for_main(main, row["normal"]),
                "currency": entity.base_currency,
                "is_control_account": is_control,
                "subledger": row["subledger"],
                "is_bank_account": row["bank"],
                "allow_manual_posting": not is_control,
                "is_postable": True,
            },
        )
        accounts_created += int(was_created)

    return {"groups_created": groups_created, "accounts_created": accounts_created}
