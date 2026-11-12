"""Read-only access to the CRM database on behalf of one CRM user.

Every call opens its own connection as the crm_reader role, starts a read-only transaction,
tells PostgreSQL who is asking (two transaction-local settings that the row-level security
policies read), runs one statement and rolls back. Nothing here trusts the SQL it is given:
the limits are enforced by the database.
"""

import os
import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

import psycopg
from psycopg import sql

ROW_CAP = 1000
STATEMENT_TIMEOUT_MS = 10_000
SAMPLE_ROWS = 5


@dataclass(frozen=True)
class Identity:
    user_id: int
    role: str  # "admin" or "user"


class QueryError(Exception):
    """A problem the model can act on: the message is returned as the tool result."""


def reader_url() -> str:
    return os.environ["READER_DATABASE_URL"]


def plain(value):
    """Values as JSON can carry them."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    return value


def run_as(identity: Identity, statement, params: tuple = ()) -> dict:
    with psycopg.connect(reader_url(), autocommit=False) as connection:
        connection.read_only = True
        with connection.cursor() as cursor:
            cursor.execute(
                sql.SQL("SET LOCAL statement_timeout = {}").format(
                    sql.Literal(STATEMENT_TIMEOUT_MS)
                )
            )
            cursor.execute(
                sql.SQL("SET LOCAL app.user_id = {}").format(sql.Literal(str(identity.user_id)))
            )
            cursor.execute(
                sql.SQL("SET LOCAL app.user_role = {}").format(sql.Literal(identity.role))
            )
            try:
                # prepare=True uses the extended protocol, which refuses more than one statement.
                cursor.execute(statement, params or None, prepare=True)
            except psycopg.errors.QueryCanceled as error:
                raise QueryError(
                    "The query took longer than 10 seconds and was cancelled."
                ) from error
            except psycopg.Error as error:
                message = (error.diag.message_primary if error.diag else None) or str(error)
                raise QueryError(f"PostgreSQL rejected the query: {message}") from error
            if cursor.description is None:
                raise QueryError("Only queries that return rows are allowed.")
            columns = [column.name for column in cursor.description]
            rows = cursor.fetchmany(ROW_CAP + 1)
        connection.rollback()
    return {
        "columns": columns,
        "rows": [[plain(value) for value in row] for row in rows[:ROW_CAP]],
        "row_count": min(len(rows), ROW_CAP),
        "truncated": len(rows) > ROW_CAP,
    }


def run_query(identity: Identity, query: str) -> dict:
    query = query.strip().rstrip(";").strip()
    if not re.match(r"(?is)^(select|with)\b", query):
        raise QueryError("Only SELECT statements are allowed (they may start with WITH).")
    if re.search(r"(?i)\b(pg_catalog|information_schema|pg_[a-z_]+)\b", query):
        raise QueryError("System catalogs are off limits. Use describe_schema to see the tables.")
    return {"sql": query, **run_as(identity, query)}


def describe_schema(identity: Identity) -> dict:
    """Tables and columns this role may read, with foreign keys. Filtered by PostgreSQL itself:
    information_schema only lists what the current role has privileges on."""
    columns = run_as(
        identity,
        """
        SELECT table_name, column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_schema = 'public'
        ORDER BY table_name, ordinal_position
        """,
    )["rows"]
    foreign_keys = run_as(
        identity,
        """
        SELECT source.relname, attribute.attname, target.relname
        FROM pg_constraint AS c
        JOIN pg_class AS source ON source.oid = c.conrelid
        JOIN pg_class AS target ON target.oid = c.confrelid
        JOIN pg_attribute AS attribute
          ON attribute.attrelid = c.conrelid AND attribute.attnum = c.conkey[1]
        WHERE c.contype = 'f' AND c.connamespace = 'public'::regnamespace
        """,
    )["rows"]
    references = {(table, column): target for table, column, target in foreign_keys}

    tables: dict[str, list[dict]] = {}
    for table, column, data_type, nullable in columns:
        entry = {"name": column, "type": data_type, "nullable": nullable == "YES"}
        if (table, column) in references:
            entry["references"] = f"{references[(table, column)]}.id"
        tables.setdefault(table, []).append(entry)
    return {
        "tables": tables,
        "notes": [
            "deals.stage is one of: lead, qualified, proposal, negotiation, won, lost.",
            "A deal is closed when stage is won or lost; closed_at is when that happened.",
            "activities.type is one of: note, call, meeting, task. An open task has "
            "completed_at IS NULL; it is overdue when due_date < current_date.",
            "deals.owner_id and activities.owner_id point to users.id (the salesperson).",
            "Money is in US dollars. Rows you cannot see for this user are already filtered out.",
        ],
    }


def sample_rows(identity: Identity, table: str) -> dict:
    schema = describe_schema(identity)["tables"]
    if table not in schema:
        raise QueryError(f"Unknown table {table!r}. Tables: {', '.join(sorted(schema))}.")
    columns = sql.SQL(", ").join(sql.Identifier(column["name"]) for column in schema[table])
    statement = sql.SQL("SELECT {} FROM {} LIMIT {}").format(
        columns, sql.Identifier(table), sql.Literal(SAMPLE_ROWS)
    )
    return run_as(identity, statement)
