"""
Integration tests for FastAPI REST Endpoints and Event Logging.
"""

import pytest
from fastapi.testclient import TestClient
from backend.app import app
from backend.database import db
from backend.models import SimulationScenario, RiskLevel, ValveState


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_api_health_endpoint(client):
    """Verify /api/health returns healthy status."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database_connected"] is True
    assert "version" in data


def test_api_status_endpoint(client):
    """Verify /api/status returns valid system state snapshot."""
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert "risk_level" in data
    assert "raw_gas" in data
    assert "filtered_gas" in data
    assert "valve_state" in data
    assert "thresholds" in data
    assert "sensor_health" in data


def test_api_sensors_endpoint(client):
    """Verify /api/sensors returns telemetry list."""
    response = client.get("/api/sensors?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_api_events_and_filtering(client):
    """Verify /api/events endpoint and query parameter filtering."""
    # Insert test events directly
    db.log_event("GAS_WARNING", 220.0, "WARNING", "OPEN", "Test warning event")
    db.log_event("AUTOMATIC_SHUTOFF", 450.0, "DANGER", "CLOSED", "Test shutoff event")

    # Fetch all
    response = client.get("/api/events?limit=20")
    assert response.status_code == 200
    events = response.json()
    assert len(events) >= 2

    # Filter by event_type
    filtered_res = client.get("/api/events?event_type=AUTOMATIC_SHUTOFF")
    assert filtered_res.status_code == 200
    filtered_events = filtered_res.json()
    assert all(e["event_type"] == "AUTOMATIC_SHUTOFF" for e in filtered_events)


def test_api_analytics_endpoint(client):
    """Verify /api/analytics returns aggregated safety summary."""
    response = client.get("/api/analytics")
    assert response.status_code == 200
    data = response.json()
    assert "max_gas_ppm" in data
    assert "avg_gas_ppm" in data
    assert "warning_count" in data
    assert "shutoff_count" in data
    assert "hourly_trends" in data


def test_api_simulation_control(client):
    """Verify start/stop simulation endpoints."""
    # Stop
    res_stop = client.post("/api/simulation/stop")
    assert res_stop.status_code == 200
    assert res_stop.json()["status"] == "STOPPED"

    # Start
    res_start = client.post("/api/simulation/start")
    assert res_start.status_code == 200
    assert res_start.json()["status"] == "RUNNING"


def test_api_scenario_switch(client):
    """Verify changing operational scenario."""
    res = client.post("/api/scenario", json={"scenario": "SLOW_LEAK"})
    assert res.status_code == 200
    data = res.json()
    assert data["scenario"] == "SLOW_LEAK"

    # Reset back to NORMAL
    client.post("/api/scenario", json={"scenario": "NORMAL"})


def test_api_valve_manual_controls_and_validation(client):
    """Verify manual valve operations and confirmation requirement."""
    # 1. Unconfirmed close should be rejected with 400
    res_bad = client.post("/api/valve/close", json={"confirmed": False})
    assert res_bad.status_code == 400

    # 2. Confirmed close succeeds
    res_close = client.post("/api/valve/close", json={"confirmed": True})
    assert res_close.status_code == 200
    assert res_close.json()["valve_state"] == "CLOSED"

    # 3. System Reset
    res_reset = client.post("/api/system/reset", json={"confirmed": True})
    assert res_reset.status_code == 200
    assert res_reset.json()["valve_state"] == "OPEN"
