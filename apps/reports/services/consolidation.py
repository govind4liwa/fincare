"""Group consolidation with intercompany elimination (design doc 05).

Group scope sums balances across the entities in the consolidation tree
(``Entity.parent_entity``). Intercompany due-to / due-from accounts registered in
``tenants.IntercompanyMap`` are netted out so group figures exclude internal
trading — same-VAT-group intra-group supplies are already out-of-scope for VAT
(ADR-0006).
"""

from apps.tenants.models import Entity, IntercompanyMap

from .balances import trial_balance
from .statements import balance_sheet, profit_and_loss


def consolidation_entities(parent):
    """The parent entity plus its consolidation subtree (one level + recursive)."""
    ids = [parent.id]
    stack = list(Entity.objects.filter(parent_entity=parent, is_active=True))
    while stack:
        node = stack.pop()
        ids.append(node.id)
        stack.extend(Entity.objects.filter(parent_entity=node, is_active=True))
    return ids


def intercompany_account_ids(entity_ids):
    """Due-to / due-from account ids for intercompany pairs wholly inside the group."""
    ids = set(entity_ids)
    maps = IntercompanyMap.objects.filter(
        from_entity_id__in=ids, to_entity_id__in=ids, is_active=True
    )
    account_ids = set()
    for m in maps:
        if m.due_to_account_id:
            account_ids.add(m.due_to_account_id)
        if m.due_from_account_id:
            account_ids.add(m.due_from_account_id)
    return account_ids


def consolidated_trial_balance(*, entity_ids, period, basis="accrual", eliminate=True):
    """Consolidated TB across entities, optionally eliminating intercompany accounts."""
    exclude = intercompany_account_ids(entity_ids) if eliminate else set()
    return trial_balance(
        entity_ids=entity_ids, period=period, basis=basis, exclude_account_ids=exclude
    )


def consolidated_statements(*, entity_ids, period, basis="accrual", eliminate=True):
    """Consolidated TB + P&L + BS. (Intercompany accounts are balance-sheet items,
    so eliminating them does not distort P&L for Phase 1.)"""
    tb = consolidated_trial_balance(
        entity_ids=entity_ids, period=period, basis=basis, eliminate=eliminate
    )
    return {
        "trial_balance": tb,
        "profit_and_loss": profit_and_loss(entity_ids=entity_ids, period=period, basis=basis),
        "balance_sheet": balance_sheet(entity_ids=entity_ids, period=period, basis=basis),
    }
