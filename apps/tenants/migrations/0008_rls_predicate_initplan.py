"""Re-create the entity-scoped RLS policies with a faster, equivalent predicate.

Same rows visible, far less work per row. Benchmarked on 1.2M journal lines
across 25 entities, group reports under RLS went from ~11s to ~5s from this
change alone. See ``rls.entity_predicate_sql`` for the two details that matter:
cast the *array* to uuid[] (not the column to text, which defeated the index),
and wrap each GUC read in a scalar subquery so Postgres evaluates it once per
query instead of once per row.

Child policies (0007) are unchanged — they reference their parent's policy,
which is now cheap, so they get faster without being touched.

``enable_policy_sql`` drops and re-creates, so this is idempotent. Safe to
apply: only requests under the restricted role see any difference, still
gated by ``RLS_ENABLED``.
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
        ("tenants", "0007_rls_child_tables"),
    ]

    operations = _policy_operations()
