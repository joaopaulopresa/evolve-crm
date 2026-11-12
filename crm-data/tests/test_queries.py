"""Run against a migrated CRM database with the demo data loaded:

    READER_DATABASE_URL=postgresql://crm_reader:...@db:5432/crm pytest

The demo users are: id of admin@evolve.test (admin) and priya@evolve.test (sales).
"""

import os

import psycopg
import pytest

from crm_data.queries import Identity, QueryError, describe_schema, run_query, sample_rows


def user(email: str) -> Identity:
    with psycopg.connect(os.environ["READER_DATABASE_URL"]) as connection:
        user_id, role = connection.execute(
            "SELECT id, role FROM users WHERE email = %s", (email,)
        ).fetchone()
    return Identity(user_id, role)


@pytest.fixture(scope="module")
def admin() -> Identity:
    return user("admin@evolve.test")


@pytest.fixture(scope="module")
def priya() -> Identity:
    return user("priya@evolve.test")


def count(identity: Identity, table: str) -> int:
    return run_query(identity, f"SELECT count(*) FROM {table}")["rows"][0][0]


def test_admin_sees_all_deals_and_a_sales_user_only_their_own(admin, priya):
    owners = run_query(priya, "SELECT DISTINCT owner_id FROM deals")["rows"]

    assert count(admin, "deals") >= 80
    assert 0 < count(priya, "deals") < count(admin, "deals")
    assert owners == [[priya.user_id]]
    assert count(priya, "companies") == count(admin, "companies") == 40


def test_result_has_columns_rows_and_the_sql_that_ran(admin):
    result = run_query(
        admin, "SELECT stage, sum(value) AS total FROM deals GROUP BY stage ORDER BY stage;"
    )

    assert result["columns"] == ["stage", "total"]
    assert (
        result["sql"]
        == "SELECT stage, sum(value) AS total FROM deals GROUP BY stage ORDER BY stage"
    )
    assert len(result["rows"]) == 6
    assert isinstance(result["rows"][0][1], float), "numeric values become plain numbers"
    assert result["truncated"] is False


@pytest.mark.parametrize(
    "query",
    [
        "UPDATE deals SET value = 0",
        "DELETE FROM contacts",
        "DROP TABLE deals",
        "INSERT INTO companies (name) VALUES ('x')",
        "WITH gone AS (DELETE FROM contacts RETURNING id) SELECT count(*) FROM gone",
        "SELECT 1; DELETE FROM contacts",
        "SELECT password_hash FROM users",
        "SELECT * FROM change_requests",
        "SELECT rolname FROM pg_roles",
        "SELECT * FROM information_schema.tables",
        "SET app.user_role = 'admin'",
    ],
)
def test_anything_but_a_plain_read_of_crm_tables_is_refused(admin, query):
    with pytest.raises(QueryError):
        run_query(admin, query)
    assert count(admin, "contacts") == 150, "nothing was changed"


def test_a_sales_user_cannot_become_admin_inside_a_query(priya):
    own = count(priya, "deals")

    with pytest.raises(QueryError, match="permission denied"):
        run_query(priya, "SELECT set_config('app.user_role', 'admin', true), count(*) FROM deals")
    assert count(priya, "deals") == own


def test_rows_are_capped(admin):
    result = run_query(admin, "SELECT generate_series(1, 5000) AS n")

    assert result["row_count"] == 1000
    assert result["truncated"] is True


def test_slow_queries_are_cancelled(admin, monkeypatch):
    monkeypatch.setattr("crm_data.queries.STATEMENT_TIMEOUT_MS", 200)

    with pytest.raises(QueryError, match="cancelled"):
        run_query(admin, "SELECT count(*) FROM generate_series(1, 200000000)")


def test_schema_lists_crm_tables_without_credentials_or_delivery_tables(priya):
    schema = describe_schema(priya)

    assert sorted(schema["tables"]) == ["activities", "companies", "contacts", "deals", "users"]
    user_columns = [column["name"] for column in schema["tables"]["users"]]
    assert "password_hash" not in user_columns
    owner = next(c for c in schema["tables"]["deals"] if c["name"] == "owner_id")
    assert owner["references"] == "users.id"


def test_sample_rows_respects_visibility_and_rejects_unknown_tables(priya):
    sample = sample_rows(priya, "deals")
    owner_index = sample["columns"].index("owner_id")

    assert 0 < sample["row_count"] <= 5
    assert {row[owner_index] for row in sample["rows"]} == {priya.user_id}
    assert "password_hash" not in sample_rows(priya, "users")["columns"]
    with pytest.raises(QueryError, match="Unknown table"):
        sample_rows(priya, "deals; DROP TABLE deals")
