from datetime import date

from sqlalchemy import func, select

from app.models import Activity, Company, Contact, Deal, User
from app.seed import load_seed


def count(db, model) -> int:
    return db.scalar(select(func.count(model.id)))


def test_seed_loads_the_cached_dataset(db):
    assert load_seed(db) is True

    assert count(db, User) == 5
    assert count(db, Company) == 40
    assert count(db, Contact) == 150
    assert count(db, Deal) == 80
    assert count(db, Activity) == 400


def test_seed_dates_are_relative_to_today(db):
    load_seed(db)

    won = db.scalars(select(Deal).where(Deal.stage == "won")).all()
    overdue = db.scalars(
        select(Activity).where(
            Activity.type == "task",
            Activity.completed_at.is_(None),
            Activity.due_date < date.today(),
        )
    ).all()

    assert all(deal.closed_at is not None for deal in won)
    assert max(deal.closed_at.date() for deal in won) <= date.today()
    assert overdue, "the dashboard needs a few overdue tasks to show"


def test_seed_does_nothing_when_data_already_exists(db):
    load_seed(db)

    assert load_seed(db) is False
    assert count(db, Company) == 40


def test_seeded_sales_user_can_sign_in(client, db):
    load_seed(db)

    response = client.post(
        "/api/auth/login", json={"email": "priya@evolve.test", "password": "demo1234"}
    )

    assert response.status_code == 200
    assert response.json()["user"]["name"] == "Priya Raman"
