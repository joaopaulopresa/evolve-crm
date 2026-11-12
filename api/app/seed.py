"""Load the synthetic demo dataset (seed/data.json) into an empty database.

    python -m app.seed

Dates in the file are offsets from today, so a freshly seeded demo always looks current.
"""

import json
import os
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import hash_password
from app.models import Activity, Company, Contact, Deal, User

SEED_FILE = Path(os.environ.get("SEED_FILE", Path(__file__).parents[2] / "seed" / "data.json"))
DEMO_PASSWORD = "demo1234"


def load_seed(session: Session) -> bool:
    """Returns False, without changing anything, when the database already has companies."""
    if session.scalar(select(func.count(Company.id))):
        return False
    data = json.loads(SEED_FILE.read_text())
    now = datetime.now(UTC)
    today = date.today()

    def days_ago(days: int) -> datetime:
        return now - timedelta(days=days)

    password_hash = hash_password(DEMO_PASSWORD)
    users = []
    for row in data["users"]:
        user = session.scalar(select(User).where(User.email == row["email"]))
        if user is None:
            user = User(**row, password_hash=password_hash)
            session.add(user)
        else:
            user.name = row["name"]
        users.append(user)

    companies = [Company(**row) for row in data["companies"]]
    session.add_all(companies)

    contacts = []
    for row in data["contacts"]:
        fields = {key: value for key, value in row.items() if key != "company"}
        contacts.append(Contact(**fields, company=companies[row["company"]]))
    session.add_all(contacts)

    deals = []
    for row in data["deals"]:
        closed, expected = row["closed_days_ago"], row["expected_close_in_days"]
        deals.append(
            Deal(
                title=row["title"],
                company=companies[row["company"]],
                contact=contacts[row["contact"]],
                owner=users[row["owner"]],
                stage=row["stage"],
                value=row["value"],
                created_at=days_ago(row["created_days_ago"]),
                closed_at=days_ago(closed) if closed is not None else None,
                expected_close_date=(
                    today + timedelta(days=expected) if expected is not None else None
                ),
            )
        )
    session.add_all(deals)
    session.flush()

    for row in data["activities"]:
        due = row["due_in_days"]
        occurred = days_ago(row["occurred_days_ago"])
        session.add(
            Activity(
                type=row["type"],
                subject=row["subject"],
                body=row["body"],
                contact_id=contacts[row["contact"]].id,
                deal_id=deals[row["deal"]].id if row["deal"] is not None else None,
                owner_id=users[row["owner"]].id,
                occurred_at=occurred,
                due_date=today + timedelta(days=due) if due is not None else None,
                completed_at=occurred + timedelta(days=1) if row["completed"] else None,
            )
        )
    session.commit()
    return True


if __name__ == "__main__":
    from app.db import SessionLocal

    with SessionLocal() as session:
        print("Demo data loaded." if load_seed(session) else "Database already has data.")
