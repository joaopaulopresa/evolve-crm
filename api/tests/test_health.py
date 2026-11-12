from fastapi.testclient import TestClient

from app.main import app


def test_health_reports_database_and_release():
    response = TestClient(app).get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert "release" in body
    assert "environment" in body
