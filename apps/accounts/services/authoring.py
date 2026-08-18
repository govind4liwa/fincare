"""Create Main/Sub account groups and postable Charge-code accounts (ADR-0004).

Group and account codes are composed here via ``coding`` — never typed by the
user. A Main group's segment fixes its nature (by first digit); a Sub group
hangs off an existing Main and inherits that nature, so a whole branch stays
one nature end to end — the same rule ``services.seed`` follows when it walks
a category template. An account's ``nature`` is inherited from its Sub group;
its ``normal_balance`` defaults from the Main band unless overridden. Codes
are immutable once created — corrections are a new group/account, not an edit.
"""

from django.db import IntegrityError, transaction

from apps.accounts.models import Account, AccountGroup
from apps.accounts.services import coding


class AccountError(ValueError):
    """Raised when an account cannot be composed or created."""


@transaction.atomic
def create_group(entity, *, level, segment, name, parent=None):
    """Create a Main (level 1) or Sub (level 2) account group."""
    if level == 1:
        if parent is not None:
            raise AccountError("A Main group cannot have a parent.")
        try:
            code = coding.compose_group_code(entity.numeric_code, segment)
            nature = coding.nature_for_main(segment)
        except coding.CodeError as exc:
            raise AccountError(str(exc)) from exc
    elif level == 2:
        if parent is None:
            raise AccountError("A Sub group must have a parent Main group.")
        if parent.entity_id != entity.id:
            raise AccountError("The parent group belongs to a different entity.")
        if parent.level != 1:
            raise AccountError("A Sub group's parent must be a Main group.")
        try:
            code = coding.compose_group_code(entity.numeric_code, parent.segment, segment)
        except coding.CodeError as exc:
            raise AccountError(str(exc)) from exc
        nature = parent.nature
    else:
        raise AccountError("Group level must be 1 (Main) or 2 (Sub).")

    try:
        return AccountGroup.objects.create(
            entity=entity,
            level=level,
            segment=segment,
            parent=parent,
            code=code,
            name=name,
            nature=nature,
        )
    except IntegrityError as exc:
        raise AccountError(f"A group with code {code} already exists.") from exc


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
