import pytest

from app.config import get_settings
from app.implementation.agent import Finished, Step
from app.implementation.ask import get_analyst, get_crm_data
from app.main import app
from tests.conftest import auth

QUERY = {
    "sql": "SELECT count(*) AS deals FROM deals",
    "columns": ["deals"],
    "rows": [[30]],
    "row_count": 1,
    "truncated": False,
}


class FakeAnalyst:
    def __init__(self):
        self.asked = []

    def run(self, prompt, session_id):
        self.asked.append((prompt, session_id))
        yield Step("mcp__crm_data__run_query", "")
        yield Finished(True, "You have 30 deals.\n")


class FakeCrmData:
    def __init__(self):
        self.calls = []

    def begin(self, user):
        self.calls.append(("begin", user.id, user.role))

    def end(self):
        self.calls.append(("end",))
        return [QUERY]


@pytest.fixture
def ask(client):
    analyst, crm_data = FakeAnalyst(), FakeCrmData()
    app.dependency_overrides[get_analyst] = lambda: analyst
    app.dependency_overrides[get_crm_data] = lambda: crm_data
    return analyst, crm_data


def test_answer_comes_with_the_sql_that_produced_it(client, alice, ask):
    analyst, crm_data = ask

    response = client.post(
        "/api/ask", json={"question": "How many deals do I have?"}, headers=auth(alice)
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["answer"] == "You have 30 deals."
    assert body["queries"][0]["sql"] == "SELECT count(*) AS deals FROM deals"
    assert body["queries"][0]["rows"] == [[30]]
    assert crm_data.calls == [("begin", alice.id, "user"), ("end",)], "identity set, then cleared"
    assert analyst.asked[0][0] == "How many deals do I have?"


def test_follow_up_questions_continue_the_conversation(client, alice, ask):
    analyst, _ = ask
    first = client.post(
        "/api/ask", json={"question": "How many deals?"}, headers=auth(alice)
    ).json()

    client.post(
        "/api/ask",
        json={"question": "And how many are won?", "conversation_id": first["conversation_id"]},
        headers=auth(alice),
    )

    assert analyst.asked[0][1] == analyst.asked[1][1] == first["conversation_id"]


def test_a_user_cannot_continue_someone_elses_conversation(client, alice, bob, ask):
    analyst, _ = ask
    hers = client.post("/api/ask", json={"question": "How many deals?"}, headers=auth(alice)).json()

    his = client.post(
        "/api/ask",
        json={"question": "What did we talk about?", "conversation_id": hers["conversation_id"]},
        headers=auth(bob),
    ).json()

    assert his["conversation_id"] != hers["conversation_id"]
    assert his["conversation_id"].startswith(f"ask-{bob.id}-")


def test_the_identity_is_cleared_even_when_the_analyst_fails(client, alice, ask):
    analyst, crm_data = ask
    analyst.run = lambda prompt, session_id: iter([Finished(False, "model error")])

    response = client.post("/api/ask", json={"question": "How many deals?"}, headers=auth(alice))

    assert response.status_code == 502
    assert crm_data.calls[-1] == ("end",)


def test_ask_needs_a_signed_in_user(client, ask):
    assert client.post("/api/ask", json={"question": "How many deals?"}).status_code == 401


def test_ask_can_be_switched_off(client, alice, monkeypatch):
    monkeypatch.setattr(get_settings(), "ask_enabled", False)

    response = client.post("/api/ask", json={"question": "How many deals?"}, headers=auth(alice))

    assert response.status_code == 503
    assert "switched off" in response.json()["detail"]


def test_ask_explains_when_the_environment_is_not_connected(client, alice):
    response = client.post("/api/ask", json={"question": "How many deals?"}, headers=auth(alice))

    assert response.status_code == 503
    assert "not connected" in response.json()["detail"]
