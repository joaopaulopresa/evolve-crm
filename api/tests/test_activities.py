from datetime import date, timedelta

from tests.conftest import auth
from tests.test_deals import create_deal


def create_contact(client, user):
    response = client.post(
        "/api/contacts", json={"first_name": "Maya", "last_name": "Okafor"}, headers=auth(user)
    )
    return response.json()


def test_activity_timeline_for_a_contact_is_newest_first(client, alice):
    contact = create_contact(client, alice)
    headers = auth(alice)
    for subject, occurred_at in [
        ("Intro call", "2026-10-01T10:00:00Z"),
        ("Sent proposal", "2026-10-05T10:00:00Z"),
    ]:
        created = client.post(
            "/api/activities",
            json={
                "type": "call",
                "subject": subject,
                "contact_id": contact["id"],
                "occurred_at": occurred_at,
            },
            headers=headers,
        )
        assert created.status_code == 201, created.text

    rows = client.get(
        "/api/activities", params={"contact_id": contact["id"]}, headers=headers
    ).json()

    assert [row["subject"] for row in rows] == ["Sent proposal", "Intro call"]
    assert rows[0]["owner_name"] == "Alice"


def test_activity_needs_a_contact_or_a_deal(client, alice):
    response = client.post(
        "/api/activities", json={"type": "note", "subject": "Orphan"}, headers=auth(alice)
    )

    assert response.status_code == 422


def test_task_can_be_completed_and_reopened(client, alice):
    deal = create_deal(client, alice)
    headers = auth(alice)
    task = client.post(
        "/api/activities",
        json={
            "type": "task",
            "subject": "Send contract",
            "deal_id": deal["id"],
            "due_date": str(date.today() + timedelta(days=2)),
        },
        headers=headers,
    ).json()
    assert task["completed_at"] is None

    done = client.patch(
        f"/api/activities/{task['id']}", json={"completed": True}, headers=headers
    ).json()
    assert done["completed_at"] is not None

    reopened = client.patch(
        f"/api/activities/{task['id']}", json={"completed": False}, headers=headers
    ).json()
    assert reopened["completed_at"] is None


def test_overdue_filter_returns_open_tasks_past_due(client, alice):
    deal = create_deal(client, alice)
    headers = auth(alice)

    def task(subject, days, completed=False):
        created = client.post(
            "/api/activities",
            json={
                "type": "task",
                "subject": subject,
                "deal_id": deal["id"],
                "due_date": str(date.today() + timedelta(days=days)),
            },
            headers=headers,
        ).json()
        if completed:
            client.patch(
                f"/api/activities/{created['id']}", json={"completed": True}, headers=headers
            )

    task("Late", -3)
    task("Late but done", -3, completed=True)
    task("Future", 3)

    rows = client.get("/api/activities", params={"overdue": True}, headers=headers).json()

    assert [row["subject"] for row in rows] == ["Late"]


def test_sales_user_sees_only_own_activities(client, admin, alice, bob):
    contact = create_contact(client, alice)
    for user in (alice, bob):
        client.post(
            "/api/activities",
            json={"type": "note", "subject": f"By {user.name}", "contact_id": contact["id"]},
            headers=auth(user),
        )

    def subjects(user):
        rows = client.get("/api/activities", headers=auth(user)).json()
        return sorted(row["subject"] for row in rows)

    assert subjects(alice) == ["By Alice"]
    assert subjects(admin) == ["By Alice", "By Bob"]
