"""The read-only database role behind the Ask tab: what it can see is decided here, in
PostgreSQL, and not by the prompt."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.models import Activity, Company, Contact, Deal


@pytest.fixture
def data(db, admin, alice, bob):
    company = Company(name="Northwind Labs")
    contact = Contact(first_name="Maya", last_name="Okafor", company=company)
    db.add_all([company, contact])
    db.flush()
    for owner, title in [(alice, "Alice deal"), (bob, "Bob deal")]:
        deal = Deal(title=title, owner=owner, value=1000, stage="lead")
        db.add(deal)
        db.flush()
        db.add(Activity(type="note", subject=f"{title} note", deal_id=deal.id, owner=owner))
    db.commit()


def as_reader(db, user=None):
    """Switch the test's transaction to the reader role, optionally as a CRM user."""
    db.execute(text("SET LOCAL ROLE crm_reader"))
    if user is not None:
        db.execute(text(f"SET LOCAL app.user_id = '{user.id}'"))
        db.execute(text(f"SET LOCAL app.user_role = '{user.role}'"))


def titles(db) -> list[str]:
    return sorted(db.scalars(text("SELECT title FROM deals")).all())


def test_admin_reads_every_deal_and_activity(db, data, admin):
    as_reader(db, admin)

    assert titles(db) == ["Alice deal", "Bob deal"]
    assert db.scalar(text("SELECT count(*) FROM activities")) == 2


def test_sales_user_reads_only_their_own_deals_and_activities(db, data, alice):
    as_reader(db, alice)

    assert titles(db) == ["Alice deal"]
    assert db.scalars(text("SELECT subject FROM activities")).all() == ["Alice deal note"]
    assert db.scalar(text("SELECT count(*) FROM companies")) == 1, "companies are shared"
    assert db.scalar(text("SELECT count(*) FROM contacts")) == 1, "contacts are shared"


def test_without_an_identity_no_deal_is_visible(db, data):
    as_reader(db)

    assert titles(db) == []


def test_reader_cannot_write(db, data, admin):
    as_reader(db, admin)

    with pytest.raises(DBAPIError, match="permission denied"):
        db.execute(text("UPDATE deals SET value = 0"))


@pytest.mark.parametrize(
    "query",
    [
        "SELECT password_hash FROM users",
        "SELECT * FROM users",
        "SELECT * FROM change_requests",
        "SELECT * FROM change_request_events",
    ],
)
def test_reader_cannot_read_credentials_or_delivery_tables(db, data, admin, query):
    as_reader(db, admin)

    with pytest.raises(DBAPIError, match="permission denied"):
        db.execute(text(query))


def test_reader_can_read_who_the_users_are(db, data, admin):
    as_reader(db, admin)

    names = db.scalars(text("SELECT name FROM users ORDER BY name")).all()

    assert names == ["Admin", "Alice", "Bob"]


def test_a_query_cannot_promote_itself_to_admin(db, data, alice):
    as_reader(db, alice)

    with pytest.raises(DBAPIError, match="permission denied"):
        db.execute(text("SELECT set_config('app.user_role', 'admin', true), title FROM deals"))
