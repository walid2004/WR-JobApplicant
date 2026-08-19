import pytest
from fastapi.testclient import TestClient
from server import app

client = TestClient(app)

def test_api_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    assert "Portal" in response.text

def test_api_stats_endpoint():
    response = client.get("/api/stats")
    assert response.status_code == 200
    data = response.json()
    assert "avg_fit_score" in data
    assert "total_discovered" in data

def test_api_vault_endpoint():
    response = client.get("/api/vault")
    assert response.status_code == 200
    data = response.json()
    assert "profile" in data
    assert "projects" in data

def test_api_portals_endpoint():
    response = client.get("/api/portals")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
