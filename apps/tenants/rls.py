"""Helpers to generate PostgreSQL Row-Level Security SQL (ADR-0008).

Used by migrations to enable RLS + a tenant-isolation policy on a table, keyed on
an entity column. The policy is permissive when the ``app.current_entities`` GUC
is unset — so migrations, shell, and management commands are unrestricted — and
restrictive otherwise. Rows with a NULL entity column (group-wide config) are
always visible.

The "unset" test is ``NULLIF(current_setting(...), '') IS NULL``, not a bare
``IS NULL``. A custom GUC reverts to the **empty string**, not NULL, once it has
been set on a connection and that transaction has ended — so on a pooled
connection a bare IS NULL check would make an unset context match *nothing*
rather than everything. That is precisely the sentinel TenantContextMiddleware
uses for superusers, so the bare check silently returned zero rows for them on
any reused connection.
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
    NULLIF(current_setting('{GUC}', true), '') IS NULL
    OR {entity_col} IS NULL
    OR {entity_col}::text = ANY (string_to_array(current_setting('{GUC}', true), ','))
)
WITH CHECK (
    NULLIF(current_setting('{GUC}', true), '') IS NULL
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


# ---------------------------------------------------------------------------
# Tenant-scoped tables and the column that carries the entity id.
# (table, entity_column)
#
# These lists are consumed by migrations, so they are append-only in practice:
# each migration must keep applying exactly the set it applied when it was
# written. `INITIAL_SCOPED_TABLES` is frozen for 0003_rls — adding a table there
# would make 0003 try to ALTER a table that later apps have not created yet on a
# fresh database. New tables go in a new list with a new migration.
# ---------------------------------------------------------------------------

# Frozen: the set 0003_rls applied (core, tenants, settings).
INITIAL_SCOPED_TABLES = [
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

# Every remaining table with a real entity_id FK — the transactional surface
# (ADR-0008 §4). Applied by 0006_rls_transactional_tables, which re-creates the
# policies for INITIAL_SCOPED_TABLES too (to pick up the NULLIF fix).
#
# Deliberately excluded:
#   * tenants_userentitymembership — this table *defines* a user's entity scope.
#     TenantContextMiddleware reads it to build the GUC, before the restricted
#     role is assumed, so scoping it would be circular and risk locking a user
#     out of their own memberships.
#   * Child tables with no entity_id of their own (ledger_journalline,
#     ar_salesinvoiceline, banking_statementline, payroll_payslip, …). An
#     entity_id-keyed policy cannot express them; they are reachable only
#     through a scoped parent. Covering them needs a parent-join policy, whose
#     per-row subquery cost has to be weighed against the reporting budget —
#     tracked as a follow-up, not silently assumed done.
#   * Group-level reference data with no entity at all (core_currency,
#     tenants_businesscategory, tenants_vatgroup, users_user) — not row-scoped
#     by design.
#
# Note on tax_taxreturn: a VAT-group return carries entity_id NULL (the group,
# not one entity), and the policy always permits NULL. So RLS isolates the
# standalone filer case, while group returns stay scoped at the application
# layer by VAT-group membership. That is intentional, not a gap in the policy.
TRANSACTIONAL_SCOPED_TABLES = [
    ("accounts_account", "entity_id"),
    ("accounts_accountgroup", "entity_id"),
    ("accounts_taxcode", "entity_id"),
    ("ap_debitnote", "entity_id"),
    ("ap_paymentallocation", "entity_id"),
    ("ap_purchasebill", "entity_id"),
    ("ap_supplier", "entity_id"),
    ("ar_creditnote", "entity_id"),
    ("ar_customer", "entity_id"),
    ("ar_receiptallocation", "entity_id"),
    ("ar_salesinvoice", "entity_id"),
    ("audit_auditlog", "entity_id"),
    ("banking_bankaccount", "entity_id"),
    ("banking_bankstatement", "entity_id"),
    ("banking_banktransfer", "entity_id"),
    ("banking_possettlement", "entity_id"),
    ("banking_reconciliation", "entity_id"),
    ("bookings_contract", "entity_id"),
    ("bookings_trip", "entity_id"),
    ("cashbook_cashaccount", "entity_id"),
    ("cashbook_cashcount", "entity_id"),
    ("cashbook_pettycashfloat", "entity_id"),
    ("cashbook_replenishment", "entity_id"),
    ("drivers_advance", "entity_id"),
    ("drivers_driver", "entity_id"),
    ("drivers_driverclearing", "entity_id"),
    ("drivers_settlement", "entity_id"),
    ("fleet_depreciationrun", "entity_id"),
    ("fleet_vehicle", "entity_id"),
    ("fleet_vehicleloan", "entity_id"),
    ("integrations_importbatch", "entity_id"),
    ("integrations_importprofile", "entity_id"),
    ("ledger_accountingperiod", "entity_id"),
    ("ledger_journalentry", "entity_id"),
    ("payroll_advance", "entity_id"),
    ("payroll_employee", "entity_id"),
    ("payroll_gratuity", "entity_id"),
    ("payroll_leave", "entity_id"),
    ("payroll_run", "entity_id"),
    ("payroll_salarycomponent", "entity_id"),
    ("platforms_earningimport", "entity_id"),
    ("platforms_platform", "entity_id"),
    ("platforms_platformsettlement", "entity_id"),
    ("reports_balancesnapshot", "entity_id"),
    ("reports_profitsnapshot", "entity_id"),
    ("reports_reportrun", "entity_id"),
    ("reports_reportschedule", "entity_id"),
    ("reports_statementtemplate", "entity_id"),
    ("settings_driveraccountingconfig", "entity_id"),
    ("tax_corporatetaxreturn", "entity_id"),
    ("tax_taxreturn", "entity_id"),
    ("vouchers_voucher", "entity_id"),
]

# Everything RLS covers. Tests and tooling read this; migrations do not.
SCOPED_TABLES = INITIAL_SCOPED_TABLES + TRANSACTIONAL_SCOPED_TABLES
