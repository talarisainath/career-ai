"""Health, docs, and CORS behaviour."""

from __future__ import annotations


def test_health_reports_ok(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "career-ai-api"
    assert body["version"] == "1.0.0"
    assert body["careers"] == 17


def test_health_allows_configured_frontend_origin(client):
    response = client.get(
        "/api/health", headers={"Origin": "http://127.0.0.1:5500"}
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5500"


def test_health_rejects_unknown_origin(client):
    response = client.get(
        "/api/health", headers={"Origin": "https://example.invalid"}
    )
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


def test_openapi_document_covers_all_endpoints(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/health" in paths
    assert "/api/careers" in paths
    assert "/api/careers/{career_id}" in paths
    assert "/api/careers/{career_id}/roadmap" in paths
    assert "/api/recommendations" in paths


def test_swagger_docs_are_served(client):
    response = client.get("/docs")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
