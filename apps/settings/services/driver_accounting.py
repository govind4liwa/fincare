"""Driver accounting configuration: the entity's approved Driver Receivable account.

Configuring the account **is** the approval — there is no per-account flag and no
account-type change. That keeps ``Staff Advances`` a plain ``GENERAL`` asset and
leaves ``AccountType.RECEIVABLE`` meaning customer AR, while still giving driver
settlements a single, explicitly sanctioned account per entity.

Eligibility is enforced here rather than in ``Model.clean()``: ordinary ``save()``
never calls ``full_clean()``, so only a service-layer gate is binding. Serializers
mirror these rules for field-level errors but are not the authority.
"""

from apps.accounts.models import Account
from apps.settings.models import DriverAccountingConfig

#: Characteristics that identify the seeded staff-advance account without relying
#: on any entity's full code (``EEE-100-120-003`` varies by entity). Used for
#: controlled backfill and provisioning only — never as a runtime lookup.
STAFF_ADVANCE_MARKERS = {
    "sub_group__segment": "120",
    "charge_segment": "003",
    "name": "Staff Advances",
    "account_type": Account.AccountType.GENERAL,
    "is_control_account": False,
    "subledger": "",
    "sub_group__nature": "asset",
    "is_active": True,
    "is_postable": True,
}

#: Account types that can never hold a driver receivable, whatever their nature.
FORBIDDEN_TYPES = {
    Account.AccountType.BANK,
    Account.AccountType.CASH,
    Account.AccountType.FIXED_ASSET,
}


class DriverAccountingConfigError(ValueError):
    """Raised when a Driver Receivable account is ineligible or unconfigured."""


def receivable_account_error(entity, account) -> str | None:
    """Why ``account`` cannot be this entity's Driver Receivable account, else ``None``.

    Every rule lives here, returning the reason as data rather than raising it.
    Callers that want an exception use :func:`validate_receivable_account`; the API
    reports this string directly, so no exception text ever reaches a response.

    A ``GENERAL`` account passes only because the configuration itself approves
    that specific account — the type is not what qualifies it.
    """
    if account is None:
        return "A Driver Receivable account is required."
    if account.entity_id != entity.id:
        return "Driver Receivable account belongs to a different entity."
    if not account.is_active:
        return "Driver Receivable account must be active."
    if not account.is_postable:
        return "Driver Receivable account must be postable."
    if not account.allow_manual_posting:
        return "Driver Receivable account must allow manual posting."
    if account.sub_group.nature != "asset":
        return "Driver Receivable account must be an asset account."
    if account.normal_balance != "D":
        # Excludes contra-assets such as accumulated depreciation.
        return "Driver Receivable account must be debit-normal."
    if account.is_bank_account or account.account_type in FORBIDDEN_TYPES:
        return "Driver Receivable account cannot be a bank, cash, or fixed-asset account."
    if account.is_control_account:
        return (
            "Driver Receivable account cannot be a control account — settlement lines "
            "carry the driver dimension, not a party subledger."
        )
    if account.subledger:
        return "Driver Receivable account cannot belong to a customer or supplier subledger."
    return None


def validate_receivable_account(entity, account):
    """Raise unless ``account`` may be this entity's Driver Receivable account."""
    problem = receivable_account_error(entity, account)
    if problem is not None:
        raise DriverAccountingConfigError(problem)
    return account


def set_driver_receivable_account(entity, account, *, user=None):
    """Create or update an entity's configuration after validating the account.

    Written through ``all_objects`` so a soft-deleted configuration is revived
    rather than collided with: the hidden row still occupies the entity's unique
    key, so inserting a second one would fail and leave the entity permanently
    unconfigurable.
    """
    validate_receivable_account(entity, account)
    config, _ = DriverAccountingConfig.all_objects.update_or_create(
        entity=entity,
        defaults={
            "default_receivable_account": account,
            "is_deleted": False,
            "deleted_at": None,
        },
    )
    return config


def get_config(entity):
    """The live configuration, or ``None``. A soft-deleted one reads as absent."""
    return DriverAccountingConfig.objects.filter(entity=entity).first()


def resolve_receivable_account(entity):
    """The entity's configured account, or a clear error if it has none."""
    config = (
        DriverAccountingConfig.objects.filter(entity=entity)
        .select_related("default_receivable_account__sub_group")
        .first()
    )
    if config is None:
        raise DriverAccountingConfigError(
            "Driver Receivable account is not configured for this entity."
        )
    return config.default_receivable_account


def find_provisionable_account(entity, *, account_model=Account):
    """The unambiguous seeded staff-advance account for ``entity``, else ``None``.

    Returns ``None`` when there is no match or more than one — provisioning must
    never guess at another asset account.
    """
    matches = list(account_model.objects.filter(entity=entity, **STAFF_ADVANCE_MARKERS)[:2])
    return matches[0] if len(matches) == 1 else None


def provision_driver_accounting(entity):
    """Configure ``entity`` from its seeded chart of accounts. Idempotent.

    Returns the config, or ``None`` when no unambiguous account exists — the
    entity is then left unconfigured rather than pointed at something arbitrary.
    """
    existing = get_config(entity)
    if existing is not None:
        return existing
    account = find_provisionable_account(entity)
    if account is None:
        return None
    return set_driver_receivable_account(entity, account)
