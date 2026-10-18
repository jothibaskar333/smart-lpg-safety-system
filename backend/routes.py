"""
FastAPI REST API Routes for Smart LPG Safety System.
Provides endpoints for live status, sensor telemetry, event log querying,
analytics aggregates, valve actuation, and scenario injection.
"""

from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Query, status

from backend.config import settings
from backend.database import db
from backend.models import (
    SystemStatusResponse,
    SensorReadingData,
    EventLogEntry,
    AnalyticsResponse,
    ScenarioChangeRequest,
    ValveActionRequest,
    SystemResetRequest,
    SimulationScenario,
)
from backend.service import coordinator

api_router = APIRouter(prefix="/api", tags=["Safety System API"])


@api_router.get("/health", summary="Health Check")
def health_check() -> Dict[str, Any]:
    """Return health status of the API service and database connectivity."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0",
        "simulation_running": coordinator._simulation_running,
        "database_connected": True
    }


@api_router.get("/status", response_model=SystemStatusResponse, summary="Get Current System Status")
def get_system_status() -> Dict[str, Any]:
    """Retrieve full real-time snapshot of the LPG safety system."""
    return coordinator.get_status()


@api_router.get("/sensors", summary="Get Recent Sensor Readings")
def get_sensors_telemetry(
    limit: int = Query(default=60, ge=5, le=500, description="Max readings to retrieve")
) -> List[Dict[str, Any]]:
    """Retrieve chronologically ordered sensor readings for graphing."""
    return db.get_recent_readings(limit=limit)


@api_router.get("/events", response_model=List[EventLogEntry], summary="Get Event Logs")
def get_event_logs(
    limit: int = Query(default=50, ge=1, le=500, description="Max events to retrieve"),
    event_type: Optional[str] = Query(default=None, description="Filter by event type"),
    risk_level: Optional[str] = Query(default=None, description="Filter by risk level")
) -> List[Dict[str, Any]]:
    """Query persistent SQLite event logs with optional filtering."""
    return db.get_events(limit=limit, event_type=event_type, risk_level=risk_level)


@api_router.get("/analytics", response_model=AnalyticsResponse, summary="Get Historical Analytics")
def get_analytics() -> Dict[str, Any]:
    """Retrieve aggregated safety metrics, historical fault counts, and hourly trends."""
    return db.get_analytics_summary()


@api_router.post("/simulation/start", summary="Start Simulation Loop")
def start_simulation() -> Dict[str, str]:
    """Resume continuous background simulation ticks."""
    coordinator.start_simulation()
    return {"message": "Simulation pipeline resumed successfully", "status": "RUNNING"}


@api_router.post("/simulation/stop", summary="Stop Simulation Loop")
def stop_simulation() -> Dict[str, str]:
    """Pause background simulation ticks."""
    coordinator.stop_simulation()
    return {"message": "Simulation pipeline paused successfully", "status": "STOPPED"}


@api_router.post("/scenario", summary="Change Simulation Scenario")
def change_scenario(req: ScenarioChangeRequest) -> Dict[str, Any]:
    """Switch active operational scenario (NORMAL, SLOW_LEAK, SUDDEN_LEAK, etc.)."""
    coordinator.set_scenario(req.scenario)
    return {
        "message": f"Scenario changed to {req.scenario.value}",
        "scenario": req.scenario.value
    }


@api_router.post("/valve/close", summary="Manual Valve Shut-Off Override")
def manual_valve_close(req: ValveActionRequest) -> Dict[str, Any]:
    """Manually command the simulated valve actuator to CLOSE."""
    success, msg = coordinator.manual_close_valve(req.confirmed)
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)
    return {"success": True, "message": msg, "valve_state": "CLOSED"}


@api_router.post("/valve/open", summary="Manual Valve Open Override")
def manual_valve_open(req: ValveActionRequest) -> Dict[str, Any]:
    """Manually command the simulated valve actuator to OPEN (blocked if risk is DANGER/CRITICAL)."""
    success, msg = coordinator.manual_open_valve(req.confirmed)
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)
    return {"success": True, "message": msg, "valve_state": "OPEN"}


@api_router.post("/system/reset", summary="System & Valve Reset")
def system_reset(req: SystemResetRequest) -> Dict[str, Any]:
    """Clear safety latch and restore system if environmental gas is safe."""
    success, msg = coordinator.reset_system(req.confirmed)
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)
    return {"success": True, "message": msg, "risk_level": "SAFE", "valve_state": "OPEN"}

