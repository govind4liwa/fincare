"""Extend RLS to the transactional tables, and repair the unset-context check.

Two changes, both applied by re-creating every policy (``enable_policy_sql``
drops and re-creates, so this is idempotent):

1. **Coverage.** 0003_rls covered core/tenants/settings — the only tables that
   existed when RLS landed. Every app built since (accounts, ledger, vouchers,
   AR/AP, banking, cashbook, tax, fleet, drivers, bookings, platforms, payroll,
   reports, integrations, audit) carries entity_id and had no policy at all, so
   a query that forgot to filter could return another entity's rows.

2. **Correctness.** The original predicate tested ``current_setting(GUC, true)
   IS NULL`` for "no tenant context". A custom GUC reverts to the *empty string*
   rather than NULL once it has been set on a connection and that transaction
   has ended, so on a pooled connection an unset context matched **nothing**
   instead of everything — silently breaking the superuser sentinel, which is
   exactly "leave the GUC unset". Now ``NULLIF(..., '') IS NULL``. Policies on
   the 0003 tables are re-created here so existing databases get the fix.

Safe to apply: the policy permits when the context is unset, and the privileged
(migration/shell) connection bypasses RLS regardless. Behaviour only changes for
requests running under the restricted role, still gated by ``RLS_ENABLED``.

Depends on the current head of every app whose tables it touches — a policy
cannot be created before its table exists.
"""

from django.db import migrations

from apps.tenants import rls


def _policy_operations():
    return [
        migrations.RunSQL(
            rls.enable_policy_sql(table, entity_col),
            reverse_sql=rls.disable_policy_sql(table),
        )
        for table, entity_col in rls.SCOPED_TABLES
    ]


class Migration(migrations.Migration):
    dependencies = [
        ("tenants", "0005_intercompanymap_due_from_account_and_more"),
        ("accounts", "0002_alter_accountgroup_code"),
        ("ap", "0002_paymentallocation_reversed_at_and_more"),
        ("ar", "0002_receiptallocation_reversed_at_and_more"),
        ("audit", "0001_initial"),
        ("banking", "0001_initial"),
        ("bookings", "0002_initial"),
        ("cashbook", "0001_initial"),
        ("drivers", "0006_backfill_settlement_receivable_balance"),
        ("fleet", "0003_alter_loanschedule_annual_interest_rate_and_more"),
        ("integrations", "0001_initial"),
        ("ledger", "0001_initial"),
        ("payroll", "0001_initial"),
        ("platforms", "0001_initial"),
        ("reports", "0001_initial"),
        ("settings", "0005_driveraccountingconfig_default_write_off_account"),
        ("tax", "0001_initial"),
        ("vouchers", "0001_initial"),
    ]

    operations = _policy_operations()
