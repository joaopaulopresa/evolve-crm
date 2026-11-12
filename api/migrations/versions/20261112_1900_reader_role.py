"""read-only role and row-level security for the Ask tab

Revision ID: 7d2a41c0b9e3
Revises: 4501faf01932
"""

from alembic import op

revision = "7d2a41c0b9e3"
down_revision = "4501faf01932"
branch_labels = None
depends_on = None

# Same rule as app/visibility.py: admins see everything, sales users see their own rows.
# The identity comes from two settings the crm-data server sets for each query.
VISIBLE = """
    current_setting('app.user_role', true) = 'admin'
    OR owner_id = NULLIF(current_setting('app.user_id', true), '')::int
"""


def upgrade() -> None:
    # Roles belong to the server, not to one database, so the role may already exist.
    op.execute(
        """
        DO $$ BEGIN
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'crm_reader') THEN
                CREATE ROLE crm_reader NOLOGIN;
            END IF;
        END $$
        """
    )
    op.execute("GRANT USAGE ON SCHEMA public TO crm_reader")
    op.execute("GRANT SELECT ON companies, contacts, deals, activities TO crm_reader")
    # Never the password hash.
    op.execute("GRANT SELECT (id, name, email, role, is_active, created_at) ON users TO crm_reader")

    for table in ("deals", "activities"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {table}_reader ON {table} FOR SELECT TO crm_reader USING ({VISIBLE})"
        )

    # A query must not be able to change who it runs as. SET is a statement of its own (and
    # crm-data allows one statement per call), but set_config() could hide inside a SELECT.
    op.execute("REVOKE EXECUTE ON FUNCTION pg_catalog.set_config(text, text, boolean) FROM PUBLIC")


def downgrade() -> None:
    op.execute("GRANT EXECUTE ON FUNCTION pg_catalog.set_config(text, text, boolean) TO PUBLIC")
    for table in ("deals", "activities"):
        op.execute(f"DROP POLICY IF EXISTS {table}_reader ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    op.execute("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM crm_reader")
    op.execute("REVOKE USAGE ON SCHEMA public FROM crm_reader")
