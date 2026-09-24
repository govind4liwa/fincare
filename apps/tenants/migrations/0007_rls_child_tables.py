"""Close the last RLS gap: child tables with no entity_id of their own.

0006 covered every table carrying ``entity_id``. The 24 tables here do not have
one — journal lines, invoice/bill/voucher lines, statement lines, payslips and
their lines, documents, schedules — and were reachable only through a scoped
parent. An unfiltered query aimed straight at one still returned every entity's
rows, which for ``ledger_journalline`` means the actual money.

Each gets a "my parent row is visible to you" policy. PostgreSQL applies the
parent's own policy inside that subquery, so the unset-context case, NULL-entity
rows and multi-level chains all compose from the parent rather than being
restated — a grandchild (payslip line -> payslip -> run) needs one level of
EXISTS, not a nested one.

Measured before choosing this over denormalising ``entity_id`` onto each child:
see the rationale on ``rls.CHILD_SCOPED_TABLES``.

Safe to apply: behaviour changes only for requests under the restricted role,
still gated by ``RLS_ENABLED``, and an unset context remains unrestricted.
"""

from django.db import migrations

from apps.tenants import rls


def _policy_operations():
    return [
        migrations.RunSQL(
            rls.enable_child_policy_sql(table, parent, fk),
            reverse_sql=rls.disable_policy_sql(table),
        )
        for table, parent, fk in rls.CHILD_SCOPED_TABLES
    ]


class Migration(migrations.Migration):
    dependencies = [
        ("tenants", "0006_rls_transactional_tables"),
    ]

    operations = _policy_operations()
