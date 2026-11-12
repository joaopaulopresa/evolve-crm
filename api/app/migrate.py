"""Apply pending migrations when the container starts.

    python -m app.migrate

After a rollback the database is ahead of the code: it carries revisions this release has
never heard of. Migrations are required to be backward compatible, so the right thing to do
is to leave the schema alone and start.
"""

import os

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import text

from app.db import engine


def database_is_ahead(database_heads: tuple[str, ...], known_revisions: set[str]) -> bool:
    return any(revision not in known_revisions for revision in database_heads)


def migrate() -> bool:
    """Returns False when the database is ahead of this release and nothing was applied."""
    config = Config("alembic.ini")
    known = {script.revision for script in ScriptDirectory.from_config(config).walk_revisions()}
    with engine.connect() as connection:
        heads = MigrationContext.configure(connection).get_current_heads()
    if database_is_ahead(heads, known):
        print(f"Database is at {', '.join(heads)}, newer than this release: schema left as is.")
        return False
    command.upgrade(config, "head")
    return True


def enable_reader_login() -> None:
    """The read-only role is created by a migration without a way to log in. The crm-data
    server needs one: give the role this installation's password (CRM_READER_PASSWORD)."""
    password = os.environ.get("CRM_READER_PASSWORD")
    if not password:
        return
    with engine.begin() as connection:
        if connection.scalar(text("SELECT 1 FROM pg_roles WHERE rolname = 'crm_reader'")):
            quoted = password.replace("'", "''")
            connection.execute(text(f"ALTER ROLE crm_reader LOGIN PASSWORD '{quoted}'"))


if __name__ == "__main__":
    migrate()
    enable_reader_login()
