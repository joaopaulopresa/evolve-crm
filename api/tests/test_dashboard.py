from datetime import date, timedelta

from tests.conftest import auth
from tests.test_deals import create_deal


def test_dashboard_summarises_pipeline_wins_and_overdue_tasks(client, admin, alice, bob):
    create_deal(client, alice, title="A1", value=1000, stage="lead")
    create_deal(client, alice, title="A2", value=2500, stage="lead")
    create_deal(client, bob, title="B1", value=4000, stage="proposal")
    won = create_deal(client, bob, title="B2", value=9000, stage="lead")
    client.patch(f"/api/deals/{won['id']}", json={"stage": "won"}, headers=auth(bob))
    client.post(
        "/api/activities",
        json={
            "type": "task",
            "subject": "Call back",
            "deal_id": won["id"],
            "due_date": str(date.today() - timedelta(days=1)),
        },
        headers=auth(bob),
    )

    body = client.get("/api/dashboard", headers=auth(admin)).json()

    pipeline = {row["stage"]: row for row in body["pipeline"]}
    assert list(pipeline) == ["lead", "qualified", "proposal", "negotiation"]
    assert pipeline["lead"] == {"stage": "lead", "count": 2, "value": 3500}
    assert pipeline["proposal"]["value"] == 4000
    assert pipeline["qualified"] == {"stage": "qualified", "count": 0, "value": 0}
    assert body["won_this_month"] == {"count": 1, "value": 9000}
    assert [task["subject"] for task in body["overdue_tasks"]] == ["Call back"]


def test_dashboard_for_a_sales_user_counts_only_their_records(client, alice, bob):
    create_deal(client, alice, value=1000)
    create_deal(client, bob, value=4000)

    body = client.get("/api/dashboard", headers=auth(alice)).json()

    assert body["pipeline"][0] == {"stage": "lead", "count": 1, "value": 1000}
    assert body["won_this_month"] == {"count": 0, "value": 0}
