"""Helpers to generate PostgreSQL Row-Level Security SQL (ADR-0008).

Used by migrations to enable RLS + a tenant-isolation policy on a table, keyed on
an entity column. The policy is permissive when the ``app.current_entities`` GUC
is unset (NULL) — so migrations, shell, and management commands are unrestricted —
and restrictive otherwise. Rows with a NULL entity column (group-wide config) are
always visible.
"""

GUC = "app.current_entities"


def enable_policy_sql(
    table: str, entity_col: str = "entity_id", *, policy: str | None = None
) -> str:
    """SQL to enable + force RLS on ``table`` and create its isolation policy."""
    policy_name = policy or f"{table}_rls"
    return f"""
ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS {policy_name} ON {table};
CREATE POLICY {policy_name} ON {table}
USING (
    current_setting('{GUC}', true) IS NULL
    OR {entity_col} IS NULL
    OR {entity_col}::text = ANY (string_to_array(current_setting('{GUC}', true), ','))
)
WITH CHECK (
    current_setting('{GUC}', true) IS NULL
    OR {entity_col} IS NULL
    OR {entity_col}::text = ANY (string_to_array(current_setting('{GUC}', true), ','))
);
""".strip()


def disable_policy_sql(table: str, *, policy: str | None = None) -> str:
    policy_name = policy or f"{table}_rls"
    return f"""
DROP POLICY IF EXISTS {policy_name} ON {table};
ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;
ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;
""".strip()


# Tenant-scoped tables and the column that carries the entity id.
# (table, entity_column)
SCOPED_TABLES = [
    ("core_numbersequence", "entity_id"),
    ("core_attachment", "entity_id"),
    ("tenants_entity", "id"),  # an entity row is scoped by its own id
    ("tenants_branch", "entity_id"),
    ("tenants_costcenter", "entity_id"),
    ("tenants_department", "entity_id"),
    ("settings_entitysetting", "entity_id"),
    ("settings_numberingseries", "entity_id"),
    ("settings_vatconfig", "entity_id"),
    ("settings_featureflag", "entity_id"),
]
