import pytest
from fastapi.testclient import TestClient
from server import app

client = TestClient(app)

def test_api_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    assert "ZM Job Applicant" in response.text or "Portal" in response.text

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

def test_api_models_endpoint():
    response = client.get("/api/models")
    assert response.status_code == 200
    data = response.json()
    assert "models" in data
    assert "current_model" in data
    assert len(data["models"]) > 0

def test_api_update_model_endpoint():
    response = client.post("/api/settings/model", json={"model": "llama3.2:latest"})
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "ok"
    assert data.get("model") == "llama3.2:latest"
