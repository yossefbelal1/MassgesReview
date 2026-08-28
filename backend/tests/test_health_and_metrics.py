import pytest

def test_liveness_endpoint(client):
    response = client.get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.json()["status"] in ["LIVE", "alive"]

def test_health_dependencies_endpoint(client):
    response = client.get("/api/v1/health/deps")
    assert response.status_code in [200, 503]
    data = response.json()
    assert "services" in data
    assert "database" in data["services"]
    assert "api" in data["services"]
    assert "telegram_engine" in data["services"]
