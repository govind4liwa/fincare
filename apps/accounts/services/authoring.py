"""Create postable Charge-code accounts under an existing Sub group (ADR-0004).

The full ``EEE-MMM-SSS-CCC`` code is composed here via ``coding`` — never typed
by the user. ``nature`` is inherited from the Sub group; ``normal_balance``
defaults from the Main band unless overridden. Codes are immutable once created,
so editing an account never changes its code (corrections = a new account).
"""

from django.db import IntegrityError, transaction

from apps.accounts.models import Account, AccountGroup
from apps.accounts.services import coding


class AccountError(ValueError):
    """Raised when an account cannot be composed or created."""


def _main_sub_segments(sub_group: AccountGroup):
    """Return the (Main, Sub) 3-digit segments for a level-2 (Sub) group.

    Derived from the group's own ``EEE-MMM-SSS`` code, so no parent lookup.
    """
    if sub_group.level != 2:
        raise AccountError("Accounts must hang off a level-2 (Sub) group.")
    parts = sub_group.code.split("-")
    if len(parts) != 3:
        raise AccountError(f"Malformed sub-group code {sub_group.code!r}.")
    return parts[1], parts[2]


@transaction.atomic
def create_account(
    entity,
    *,
    sub_group,
    charge_segment,
    name,
    account_type,
    normal_balance="",
    currency=None,
    is_control_account=False,
    subledger="",
    is_bank_account=False,
    allow_manual_posting=True,
    is_postable=True,
    is_active=True,
):
    if sub_group.entity_id != entity.id:
        raise AccountError("The Sub group belongs to a different entity.")

    main, sub = _main_sub_segments(sub_group)
    try:
        # compose_account_code validates every segment is 3 digits.
        code = coding.compose_account_code(entity.numeric_code, main, sub, charge_segment)
        nb = normal_balance or coding.normal_balance_for_main(main)
    except coding.CodeError as exc:
        raise AccountError(str(exc)) from exc

    try:
        return Account.objects.create(
            entity=entity,
            sub_group=sub_group,
            charge_segment=charge_segment,
            code=code,
            name=name,
            account_type=account_type,
            normal_balance=nb,
            currency=currency or entity.base_currency,
            is_control_account=is_control_account,
            subledger=subledger,
            is_bank_account=is_bank_account,
            allow_manual_posting=allow_manual_posting,
            is_postable=is_postable,
            is_active=is_active,
        )
    except IntegrityError as exc:
        raise AccountError(f"An account with code {code} already exists.") from exc
