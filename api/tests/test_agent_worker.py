"""The change-request worker, with a fake agent in place of Hermes."""

import pytest

from app.config import get_settings
from app.implementation.agent import Finished, Step, Usage
from app.implementation.factory import get_factory
from app.implementation.worker import classify, clean, describe, process_next, recover_interrupted
from app.main import app
from tests.conftest import auth
from tests.test_change_requests import KEY, SHA, FakeFactory

SUBMITTED = (
    "- Contacts now have a lead source.\n- The contacts list can be filtered by it.\n\n"
    "RESULT: submitted"
)


class FakeAgent:
    """Replays a scripted run and remembers what it was asked."""

    def __init__(self, *runs: list):
        self.runs = list(runs)
        self.prompts: list[tuple[str, str]] = []

    def run(self, prompt, session_id):
        self.prompts.append((prompt, session_id))
        yield from self.runs.pop(0)

    def usage(self, session_id):
        return Usage(tokens=12_345, cost_usd=0.0123)


@pytest.fixture
def setup(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "hermes_builder_url", "http://hermes-builder:8642")
    monkeypatch.setattr(get_settings(), "langfuse_public_url", "http://localhost:3300")
    app.dependency_overrides[get_factory] = lambda: FakeFactory()


def open_request(client, admin, text="Add a lead source field to contacts"):
    response = client.post("/api/change-requests", json={"description": text}, headers=auth(admin))
    assert response.status_code == 201, response.text
    return response.json()


def detail(client, admin, request_id):
    return client.get(f"/api/change-requests/{request_id}", headers=auth(admin)).json()


def test_a_new_request_is_queued_for_the_agent(client, admin, setup):
    assert open_request(client, admin)["status"] == "queued"


def test_the_agent_gets_the_request_and_its_steps_and_reply_are_recorded(client, db, admin, setup):
    request = open_request(client, admin)
    agent = FakeAgent(
        [
            Step("terminal", f"evolve-start {request['id']}"),
            Step("read_file", "api/app/models.py"),
            Step("todo", ""),
            Step("patch", "api/app/models.py"),
            Step("terminal", 'evolve-submit "feat: add lead source to contacts"'),
            Finished(True, SUBMITTED, tokens=9000),
        ]
    )

    assert process_next(db, agent) is True

    prompt, session_id = agent.prompts[0]
    assert "Add a lead source field to contacts" in prompt
    assert f"evolve-start {request['id']}" in prompt
    assert session_id.startswith(f"cr-{request['id']}-")
    after = detail(client, admin, request["id"])
    assert after["status"] == "checking", "submitted: now waiting for the pipeline"
    assert after["summary"].startswith("- Contacts now have a lead source.")
    assert "RESULT" not in after["summary"]
    assert (after["tokens"], after["cost_usd"]) == (12_345, 0.0123)
    assert after["trace_url"] == f"http://localhost:3300/project/evolve-crm/sessions/{session_id}"
    assert [(e["kind"], e["message"]) for e in after["events"]][1:6] == [
        ("agent_started", "Hermes started working."),
        ("agent_step", f"Ran: evolve-start {request['id']}"),
        ("agent_step", "Read api/app/models.py"),
        ("agent_step", "Edited api/app/models.py"),
        ("agent_step", 'Ran: evolve-submit "feat: add lead source to contacts"'),
    ]
    assert process_next(db, agent) is False, "nothing else is queued"


def test_pipeline_progress_during_the_run_is_not_overwritten(client, db, admin, setup):
    request = open_request(client, admin)

    def run_with_pipeline():
        yield Step("terminal", "evolve-submit")
        client.post(
            "/api/internal/pipeline-events",
            json={
                "kind": "preview_ready",
                "change_request_id": request["id"],
                "sha": SHA,
                "url": "http://localhost:8201",
            },
            headers=KEY,
        )
        yield Finished(True, SUBMITTED)

    process_next(db, FakeAgent(run_with_pipeline()))

    assert detail(client, admin, request["id"])["status"] == "preview_ready"


def test_a_question_waits_for_the_owner_and_the_reply_continues_the_same_session(
    client, db, admin, setup
):
    request = open_request(client, admin, "Add a priority to deals")
    agent = FakeAgent(
        [Finished(True, "QUESTION: Which priorities do you want: low, medium, high?")],
        [Step("terminal", "evolve-submit"), Finished(True, SUBMITTED)],
    )
    process_next(db, agent)

    waiting = detail(client, admin, request["id"])
    assert waiting["status"] == "needs_input"
    assert waiting["events"][-1]["kind"] == "agent_question"
    assert waiting["events"][-1]["message"] == "Which priorities do you want: low, medium, high?"

    replied = client.post(
        f"/api/change-requests/{request['id']}/messages",
        json={"text": "Low, medium and high."},
        headers=auth(admin),
    )
    assert replied.json()["status"] == "queued"
    process_next(db, agent)

    (_, first_session), (second_prompt, second_session) = agent.prompts
    assert first_session == second_session
    assert "Low, medium and high." in second_prompt
    assert detail(client, admin, request["id"])["status"] == "checking"


def test_asking_for_an_adjustment_on_a_preview_withdraws_it_until_the_new_one_is_ready(
    client, db, admin, setup
):
    request = open_request(client, admin)
    process_next(db, FakeAgent([Finished(True, SUBMITTED)]))
    client.post(
        "/api/internal/pipeline-events",
        json={
            "kind": "preview_ready",
            "change_request_id": request["id"],
            "sha": SHA,
            "url": "http://localhost:8201",
        },
        headers=KEY,
    )

    client.post(
        f"/api/change-requests/{request['id']}/messages",
        json={"text": "Make the field a dropdown."},
        headers=auth(admin),
    )

    assert detail(client, admin, request["id"])["status"] == "queued"
    approve = client.post(f"/api/change-requests/{request['id']}/approve", headers=auth(admin))
    assert approve.status_code == 409


def test_failed_checks_go_back_to_the_agent_once_then_to_the_owner(client, db, admin, setup):
    request = open_request(client, admin)
    agent = FakeAgent([Finished(True, SUBMITTED)], [Finished(True, SUBMITTED)])
    process_next(db, agent)

    def checks_fail():
        client.post(
            "/api/internal/pipeline-events",
            json={
                "kind": "checks_failed",
                "change_request_id": request["id"],
                "sha": SHA,
                "log": "Protected paths were changed:\n  deploy/deploy.sh",
            },
            headers=KEY,
        )

    checks_fail()
    assert detail(client, admin, request["id"])["status"] == "queued"
    process_next(db, agent)
    assert "deploy/deploy.sh" in agent.prompts[1][0]

    checks_fail()
    assert detail(client, admin, request["id"])["status"] == "checks_failed"


def test_an_unreachable_agent_leaves_the_request_waiting_with_the_reason(client, db, admin, setup):
    request = open_request(client, admin)

    class Down(FakeAgent):
        def run(self, prompt, session_id):
            raise ConnectionError("connection refused")
            yield

    process_next(db, Down())

    after = detail(client, admin, request["id"])
    assert after["status"] == "needs_input"
    assert "connection refused" in after["events"][-1]["message"]


def test_only_one_request_is_in_progress_at_a_time(client, db, admin, setup):
    first = open_request(client, admin)

    second = client.post(
        "/api/change-requests", json={"description": "Another change"}, headers=auth(admin)
    )
    assert second.status_code == 409
    assert f"#{first['id']}" in second.json()["detail"]

    client.post(f"/api/change-requests/{first['id']}/discard", headers=auth(admin))
    assert open_request(client, admin, "Another change")["status"] == "queued"


def test_a_run_interrupted_by_a_restart_is_handed_back_to_the_owner(client, db, admin, setup):
    request = open_request(client, admin)
    db.execute(__import__("sqlalchemy").text("UPDATE change_requests SET status = 'working'"))
    db.commit()

    recover_interrupted(db)

    assert detail(client, admin, request["id"])["status"] == "needs_input"


@pytest.mark.parametrize(
    ("output", "meaning"),
    [
        (SUBMITTED, "submitted"),
        ("QUESTION: Which screen?", "question"),
        ("DECLINED: That is not a change to the CRM.", "declined"),
        ("I could not make the tests pass.\nRESULT: failed", "stuck"),
        ("RESULT: submitted\nActually no.", "stuck"),
    ],
)
def test_reply_meaning(output, meaning):
    assert classify(output) == meaning


def test_reply_markers_are_not_shown_to_the_owner():
    assert clean("QUESTION: Which screen?") == "Which screen?"
    assert clean("Done.\n\nRESULT: submitted") == "Done."


def test_only_meaningful_steps_are_described():
    assert describe(Step("terminal", " evolve-test ")) == "Ran: evolve-test"
    assert describe(Step("write_file", "web/src/types.ts")) == "Edited web/src/types.ts"
    assert describe(Step("todo", "")) is None


def test_features_tell_the_web_app_what_is_connected(client, admin, alice, setup, monkeypatch):
    monkeypatch.setattr(get_settings(), "factory_url", "http://deployer:8700")

    assert client.get("/api/features", headers=auth(admin)).json() == {
        "environment": "development",
        "implement": True,
        "implement_agent": True,
        "ask": False,
        "ask_disabled_by_owner": False,
    }
    assert client.get("/api/features", headers=auth(alice)).json()["implement"] is False
