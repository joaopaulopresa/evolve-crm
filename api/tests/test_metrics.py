from tests.conftest import auth
from tests.test_deals import create_deal


def metric(text: str, name: str) -> float | None:
    """Value of the first sample whose line starts with `name` (labels included)."""
    for line in text.splitlines():
        if line.startswith(name):
            return float(line.rsplit(" ", 1)[1])
    return None


def test_requests_are_counted_by_route_template_and_status(client, alice):
    deal = create_deal(client, alice)
    client.get(f"/api/deals/{deal['id']}", headers=auth(alice))
    client.get("/api/deals/999999", headers=auth(alice))

    text = client.get("/metrics").text

    ok = 'evolve_http_requests_total{method="GET",route="/api/deals/{deal_id}",status="200"}'
    missing = 'evolve_http_requests_total{method="GET",route="/api/deals/{deal_id}",status="404"}'
    assert metric(text, ok) >= 1
    assert metric(text, missing) >= 1
    assert "evolve_http_request_duration_seconds_bucket" in text
    assert "/api/deals/999999" not in text, "raw paths would create a series per id"


def test_business_numbers_are_read_from_the_database(client, db, admin, alice):
    create_deal(client, alice, stage="lead")
    create_deal(client, alice, stage="lead")
    newest = create_deal(client, alice, stage="won")
    client.post(
        "/api/internal/pipeline-events",
        json={"kind": "deployed", "sha": "a" * 40},
        headers={"X-Factory-Key": "test-factory-key"},
    )

    text = client.get("/metrics").text

    assert metric(text, 'evolve_deals{stage="lead"}') == 2
    assert metric(text, 'evolve_deals{stage="won"}') == 1
    # Ids only grow, so the highest one counts every deal ever created, deleted ones included.
    assert metric(text, "evolve_deals_created_total") == newest["id"]
    assert metric(text, 'evolve_pipeline_events_total{kind="deployed"}') == 1
    assert metric(text, 'evolve_change_requests{status="live"}') == 0


def test_metrics_are_not_served_through_the_public_api_prefix(client):
    assert client.get("/api/metrics").status_code == 404
