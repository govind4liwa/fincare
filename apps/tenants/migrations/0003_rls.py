"""Row-Level Security: restricted app role, grants, and isolation policies.

Safe to apply immediately: the privileged (superuser) connection bypasses RLS,
so behaviour is unchanged until requests run under the restricted role (gated by
settings.RLS_ENABLED). See ADR-0008.

This migration only creates the restricted role and RLS policies; it depends on
the table-creating migrations (core/tenants/settings), not on the membership
model (which is not RLS-scoped). `makemigrations tenants` will add the membership
migration as the next number after this one.
"""

from django.db import migrations

from apps.tenants import rls

ROLE_FORWARD = """
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'fincare_app') THEN
        CREATE ROLE fincare_app NOLOGIN NOSUPERUSER;
    END IF;
END
$$;
GRANT USAGE ON SCHEMA public TO fincare_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO fincare_app;
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO fincare_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO fincare_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO fincare_app;
""".strip()

# Role is cluster-level and may be shared; do not drop on reverse.
ROLE_REVERSE = "-- role/grants intentionally left in place on reverse"


def _policy_operations():
    ops = [migrations.RunSQL(ROLE_FORWARD, reverse_sql=ROLE_REVERSE)]
    for table, entity_col in rls.SCOPED_TABLES:
        ops.append(
            migrations.RunSQL(
                rls.enable_policy_sql(table, entity_col),
                reverse_sql=rls.disable_policy_sql(table),
            )
        )
    return ops


class Migration(migrations.Migration):
    dependencies = [
        ("tenants", "0001_initial"),
        ("core", "0001_initial"),
        ("settings", "0002_initial"),
    ]

    operations = _policy_operations()
