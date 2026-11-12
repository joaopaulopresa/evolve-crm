import pytest

from app.implementation.factory import get_factory
from app.main import app
from tests.conftest import auth

KEY = {"X-Factory-Key": "test-factory-key"}
SHA = "a" * 40


class FakeFactory:
    def __init__(self):
        self.calls = []

    def merge(self, change_request_id, sha):
        self.calls.append(("merge", change_request_id, sha))

    def discard(self, change_request_id):
        self.calls.append(("discard", change_request_id))

    def rollback(self, requested_by):
        self.calls.append(("rollback", requested_by))
        return {"queued": True, "target": "b" * 40}

    def releases(self):
        return {"current": SHA, "rollback_target": "b" * 40, "history": [], "busy": False}


@pytest.fixture
def factory(client):
    fake = FakeFactory()
    app.dependency_overrides[get_factory] = lambda: fake
    return fake


def open_request(client, admin, text="Add a lead source field to contacts"):
    response = client.post("/api/change-requests", json={"description": text}, headers=auth(admin))
    assert response.status_code == 201, response.text
    return response.json()


def pipeline_event(client, kind, request_id, **fields):
    payload = {"kind": kind, "change_request_id": request_id, "sha": SHA, **fields}
    response = client.post("/api/internal/pipeline-events", json=payload, headers=KEY)
    assert response.status_code == 204, response.text


def status(client, admin, request_id):
    return client.get(f"/api/change-requests/{request_id}", headers=auth(admin)).json()["status"]


def test_admin_opens_a_change_request_with_its_branch(client, admin, factory):
    request = open_request(client, admin)

    assert request["status"] == "open"
    assert request["branch"] == f"cr/{request['id']}"
    assert request["requested_by_name"] == "Admin"
    assert request["title"] == "Add a lead source field to contacts"


def test_sales_users_cannot_use_change_requests(client, alice, factory):
    headers = auth(alice)

    assert (
        client.post("/api/change-requests", json={"description": "x"}, headers=headers).status_code
        == 403
    )
    assert client.get("/api/change-requests", headers=headers).status_code == 403
    assert client.post("/api/releases/rollback", headers=headers).status_code == 403


def test_pipeline_events_need_the_factory_key(client, admin, factory):
    request = open_request(client, admin)
    payload = {"kind": "checks_started", "change_request_id": request["id"], "sha": SHA}

    assert client.post("/api/internal/pipeline-events", json=payload).status_code == 401
    assert (
        client.post(
            "/api/internal/pipeline-events", json=payload, headers={"X-Factory-Key": "wrong"}
        ).status_code
        == 401
    )


def test_pipeline_events_move_the_request_to_a_preview(client, admin, factory):
    request = open_request(client, admin)

    pipeline_event(client, "checks_started", request["id"], branch=request["branch"])
    assert status(client, admin, request["id"]) == "checking"
    pipeline_event(client, "checks_passed", request["id"], log="32 passed")
    pipeline_event(client, "preview_ready", request["id"], url="http://localhost:8201")

    detail = client.get(f"/api/change-requests/{request['id']}", headers=auth(admin)).json()
    assert detail["status"] == "preview_ready"
    assert detail["preview_url"] == "http://localhost:8201"
    assert detail["head_sha"] == SHA
    assert [event["kind"] for event in detail["events"]] == [
        "opened",
        "checks_started",
        "checks_passed",
        "preview_ready",
    ]


def test_failed_checks_keep_the_log(client, admin, factory):
    request = open_request(client, admin)

    pipeline_event(client, "checks_failed", request["id"], log="1 failed: test_contacts")

    detail = client.get(f"/api/change-requests/{request['id']}", headers=auth(admin)).json()
    assert detail["status"] == "checks_failed"
    assert "test_contacts" in detail["events"][-1]["log"]


def test_approval_is_only_possible_on_a_preview_and_asks_for_the_merge(client, admin, factory):
    request = open_request(client, admin)
    too_early = client.post(f"/api/change-requests/{request['id']}/approve", headers=auth(admin))
    pipeline_event(client, "preview_ready", request["id"], url="http://localhost:8201")

    approved = client.post(f"/api/change-requests/{request['id']}/approve", headers=auth(admin))

    assert too_early.status_code == 409
    assert approved.json()["status"] == "approved"
    assert approved.json()["approved_by_name"] == "Admin"
    assert factory.calls == [("merge", request["id"], SHA)]


def test_the_merge_gate_approves_only_the_exact_commit_that_was_reviewed(client, admin, factory):
    request = open_request(client, admin)
    url = f"/api/internal/change-requests/{request['id']}/approval"
    pipeline_event(client, "preview_ready", request["id"], url="http://localhost:8201")

    before = client.get(url, params={"sha": SHA}, headers=KEY).json()
    client.post(f"/api/change-requests/{request['id']}/approve", headers=auth(admin))

    assert before == {"approved": False}
    assert client.get(url, params={"sha": SHA}, headers=KEY).json() == {"approved": True}
    assert client.get(url, params={"sha": "c" * 40}, headers=KEY).json() == {"approved": False}
    assert client.get(url, params={"sha": SHA}).status_code == 401


def test_a_new_push_after_approval_withdraws_it(client, admin, factory):
    request = open_request(client, admin)
    pipeline_event(client, "preview_ready", request["id"], url="http://localhost:8201")
    client.post(f"/api/change-requests/{request['id']}/approve", headers=auth(admin))

    client.post(
        "/api/internal/pipeline-events",
        json={"kind": "checks_started", "change_request_id": request["id"], "sha": "c" * 40},
        headers=KEY,
    )

    url = f"/api/internal/change-requests/{request['id']}/approval"
    assert client.get(url, params={"sha": "c" * 40}, headers=KEY).json() == {"approved": False}
    assert status(client, admin, request["id"]) == "checking"


def test_deploy_events_take_the_request_live_and_rollback_marks_it(client, admin, factory):
    request = open_request(client, admin)
    pipeline_event(client, "preview_ready", request["id"], url="http://localhost:8201")
    client.post(f"/api/change-requests/{request['id']}/approve", headers=auth(admin))

    pipeline_event(client, "deploy_started", request["id"])
    assert status(client, admin, request["id"]) == "deploying"
    pipeline_event(client, "deployed", request["id"])
    assert status(client, admin, request["id"]) == "live"

    rollback = client.post("/api/releases/rollback", headers=auth(admin))
    assert rollback.status_code == 202
    assert factory.calls[-1] == ("rollback", "admin@example.test")
    pipeline_event(client, "rolled_back", request["id"])
    assert status(client, admin, request["id"]) == "rolled_back"


def test_failed_deploy_is_recorded(client, admin, factory):
    request = open_request(client, admin)
    pipeline_event(client, "preview_ready", request["id"], url="http://localhost:8201")
    client.post(f"/api/change-requests/{request['id']}/approve", headers=auth(admin))

    pipeline_event(client, "deploy_failed", request["id"], log="smoke test timed out")

    assert status(client, admin, request["id"]) == "deploy_failed"


def test_discard_removes_the_preview_and_closes_the_request(client, admin, factory):
    request = open_request(client, admin)
    pipeline_event(client, "preview_ready", request["id"], url="http://localhost:8201")

    discarded = client.post(f"/api/change-requests/{request['id']}/discard", headers=auth(admin))

    assert discarded.json()["status"] == "discarded"
    assert factory.calls == [("discard", request["id"])]
    again = client.post(f"/api/change-requests/{request['id']}/approve", headers=auth(admin))
    assert again.status_code == 409


def test_events_without_a_request_are_kept_in_the_delivery_log(client, admin, factory):
    client.post("/api/internal/pipeline-events", json={"kind": "deployed", "sha": SHA}, headers=KEY)

    releases = client.get("/api/releases", headers=auth(admin)).json()

    assert releases["current"] == SHA
    assert [event["kind"] for event in releases["events"]] == ["deployed"]


def test_without_a_factory_the_feature_says_so(client, admin):
    response = client.post(
        "/api/change-requests", json={"description": "Add a field"}, headers=auth(admin)
    )

    assert response.status_code == 503
    assert "factory" in response.json()["detail"].lower()
