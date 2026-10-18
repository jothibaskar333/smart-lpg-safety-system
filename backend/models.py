"""
Data Models and Enums for Smart LPG Leak Detection & Automatic Shut-Off System.
"""

from __future__ import annotations
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    SAFE = "SAFE"
    WARNING = "WARNING"
    DANGER = "DANGER"
    CRITICAL = "CRITICAL"


class ValveState(str, Enum):
    OPEN = "OPEN"
    CLOSING = "CLOSING"
    CLOSED = "CLOSED"


class ValveActionSource(str, Enum):
    AUTOMATIC_RULE = "AUTOMATIC_RULE"
    MANUAL_OVERRIDE = "MANUAL_OVERRIDE"
    SYSTEM_RESET = "SYSTEM_RESET"


class SensorHealthStatus(str, Enum):
    NORMAL = "NORMAL"
    WARNING = "WARNING"
    FAULT = "FAULT"


class SimulationScenario(str, Enum):
    NORMAL = "NORMAL"
    SLOW_LEAK = "SLOW_LEAK"
    SUDDEN_LEAK = "SUDDEN_LEAK"
    RAPID_SPIKE = "RAPID_SPIKE"
    NOISY_SENSOR = "NOISY_SENSOR"
    SENSOR_RECOVERY = "SENSOR_RECOVERY"
    SENSOR_FAILURE = "SENSOR_FAILURE"


class EventType(str, Enum):
    GAS_SAFE = "GAS_SAFE"
    GAS_WARNING = "GAS_WARNING"
    GAS_DANGER = "GAS_DANGER"
    GAS_CRITICAL = "GAS_CRITICAL"
    RAPID_GAS_RISE = "RAPID_GAS_RISE"
    AUTOMATIC_SHUTOFF = "AUTOMATIC_SHUTOFF"
    MANUAL_SHUTOFF = "MANUAL_SHUTOFF"
    MANUAL_OPEN = "MANUAL_OPEN"
    VALVE_RESET = "VALVE_RESET"
    SENSOR_FAULT = "SENSOR_FAULT"
    SENSOR_RECOVERY = "SENSOR_RECOVERY"
    SIMULATION_STARTED = "SIMULATION_STARTED"
    SIMULATION_STOPPED = "SIMULATION_STOPPED"
    SCENARIO_CHANGED = "SCENARIO_CHANGED"
    ANOMALY_DETECTED = "ANOMALY_DETECTED"


# ------------------------------------------------------------------------------
# Pydantic Schemas
# ------------------------------------------------------------------------------

class SensorReadingData(BaseModel):
    timestamp: str
    raw_gas: float
    filtered_gas: float
    rate_of_change: float
    rate_per_second: float
    temperature: float
    humidity: float
    sensor_status: SensorHealthStatus
    is_anomaly: bool = False
    anomaly_score: float = 0.0


class SystemStatusResponse(BaseModel):
    timestamp: str
    risk_level: RiskLevel
    raw_gas: float
    filtered_gas: float
    rate_of_change: float
    rate_per_second: float
    rapid_rise_detected: bool
    temperature: float
    humidity: float
    valve_state: ValveState
    valve_angle_deg: float
    valve_last_source: ValveActionSource
    sensor_health: SensorHealthStatus
    sensor_health_reason: str
    buzzer_state: str  # OFF, BEEPING, CONTINUOUS
    warning_led: bool
    danger_led: bool
    simulation_running: bool
    active_scenario: str
    is_anomaly: bool
    anomaly_label: str
    thresholds: Dict[str, float]


class EventLogEntry(BaseModel):
    id: Optional[int] = None
    timestamp: str
    event_type: str
    gas_value: float
    risk_level: str
    valve_state: str
    description: str


class ScenarioChangeRequest(BaseModel):
    scenario: SimulationScenario


class ValveActionRequest(BaseModel):
    confirmed: bool = Field(..., description="Explicit UI confirmation flag")


class SystemResetRequest(BaseModel):
    confirmed: bool = Field(..., description="Explicit UI confirmation flag")


class HourlyTrend(BaseModel):
    hour: str
    avg_gas: float
    max_gas: float
    readings_count: int


class AnalyticsResponse(BaseModel):
    max_gas_ppm: float
    avg_gas_ppm: float
    warning_count: int
    danger_count: int
    critical_count: int
    shutoff_count: int
    sensor_fault_count: int
    total_readings: int
    total_monitoring_seconds: float
    hourly_trends: List[HourlyTrend]
    recent_events: List[EventLogEntry]
