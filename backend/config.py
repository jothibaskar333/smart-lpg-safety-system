"""
Configuration Module for Smart LPG Leak Detection & Automatic Shut-Off System.

CRITICAL NOTICE:
This system is an academic prototype and simulation tool.
The thresholds defined here are DEMONSTRATION THRESHOLDS for educational
and prototype testing purposes only. They are NOT certified real-world
safety limits and MUST NOT be used to control real-world LPG installations.
"""

from __future__ import annotations
import os
from pathlib import Path
from dataclasses import dataclass, field
from dotenv import load_dotenv

# Base Project Directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env if present
load_dotenv(dotenv_path=BASE_DIR / ".env")


@dataclass
class SafetyThresholds:
    """
    Demonstration thresholds for LPG gas concentration risk levels (in PPM).
    All thresholds are configurable to match specific sensor calibrations.
    """
    safe_max: float = float(os.getenv("GAS_SAFE_MAX", "199.0"))
    warning_threshold: float = float(os.getenv("GAS_WARNING_THRESHOLD", "200.0"))
    danger_threshold: float = float(os.getenv("GAS_DANGER_THRESHOLD", "400.0"))
    critical_threshold: float = float(os.getenv("GAS_CRITICAL_THRESHOLD", "700.0"))
    
    # Hysteresis deadband in PPM to prevent rapid state chattering around boundaries
    hysteresis_ppm: float = float(os.getenv("GAS_HYSTERESIS_PPM", "30.0"))
    
    # Rate-of-Rise (RoR) abnormal trigger threshold in PPM / second
    rate_of_rise_threshold: float = float(os.getenv("RATE_OF_RISE_THRESHOLD", "25.0"))


@dataclass
class SensorConfig:
    """
    Sensor physical plausibility limits and filtering parameters.
    """
    min_ppm: float = float(os.getenv("SENSOR_MIN_PPM", "0.0"))
    max_ppm: float = float(os.getenv("SENSOR_MAX_PPM", "2500.0"))
    max_jump_per_sec: float = float(os.getenv("SENSOR_MAX_JUMP_PER_SEC", "350.0"))
    stuck_reading_count: int = int(os.getenv("SENSOR_STUCK_READING_COUNT", "8"))
    timeout_seconds: float = float(os.getenv("SENSOR_TIMEOUT_SECONDS", "5.0"))
    
    # Smoothing parameters
    ema_alpha: float = float(os.getenv("EMA_ALPHA", "0.25"))
    moving_average_window: int = int(os.getenv("MOVING_AVERAGE_WINDOW", "5"))


@dataclass
class MQTTConfig:
    """MQTT Broker configuration for telemetry and event streaming."""
    enabled: bool = os.getenv("MQTT_ENABLED", "False").lower() in ("true", "1", "yes")
    broker_host: str = os.getenv("MQTT_BROKER_HOST", "localhost")
    broker_port: int = int(os.getenv("MQTT_BROKER_PORT", "1883"))
    telemetry_topic: str = os.getenv("MQTT_TELEMETRY_TOPIC", "lpg_system/telemetry")
    alerts_topic: str = os.getenv("MQTT_ALERTS_TOPIC", "lpg_system/alerts")


@dataclass
class MLConfig:
    """Machine learning anomaly detector settings."""
    enabled: bool = os.getenv("ML_ANOMALY_ENABLED", "True").lower() in ("true", "1", "yes")
    contamination_rate: float = float(os.getenv("ML_CONTAMINATION_RATE", "0.05"))
    model_save_path: Path = field(default_factory=lambda: BASE_DIR / "data" / "anomaly_model.pkl")


@dataclass
class SystemConfig:
    """Main System Application Configuration."""
    host: str = os.getenv("HOST", "127.0.0.1")
    port: int = int(os.getenv("PORT", "8000"))
    debug: bool = os.getenv("DEBUG", "True").lower() in ("true", "1", "yes")
    
    database_path: Path = field(default_factory=lambda: BASE_DIR / os.getenv("DATABASE_PATH", "data/lpg_safety.db"))
    simulation_interval_sec: float = float(os.getenv("SIMULATION_INTERVAL_SEC", "1.0"))
    default_scenario: str = os.getenv("DEFAULT_SCENARIO", "NORMAL")
    
    safety: SafetyThresholds = field(default_factory=SafetyThresholds)
    sensor: SensorConfig = field(default_factory=SensorConfig)
    mqtt: MQTTConfig = field(default_factory=MQTTConfig)
    ml: MLConfig = field(default_factory=MLConfig)

    def to_dict(self) -> dict:
        """Export non-sensitive configuration to dictionary."""
        return {
            "server": {"host": self.host, "port": self.port, "debug": self.debug},
            "database_path": str(self.database_path),
            "simulation_interval_sec": self.simulation_interval_sec,
            "default_scenario": self.default_scenario,
            "safety": {
                "safe_max": self.safety.safe_max,
                "warning_threshold": self.safety.warning_threshold,
                "danger_threshold": self.safety.danger_threshold,
                "critical_threshold": self.safety.critical_threshold,
                "hysteresis_ppm": self.safety.hysteresis_ppm,
                "rate_of_rise_threshold": self.safety.rate_of_rise_threshold,
            },
            "sensor": {
                "min_ppm": self.sensor.min_ppm,
                "max_ppm": self.sensor.max_ppm,
                "max_jump_per_sec": self.sensor.max_jump_per_sec,
                "stuck_reading_count": self.sensor.stuck_reading_count,
                "timeout_seconds": self.sensor.timeout_seconds,
                "ema_alpha": self.sensor.ema_alpha,
                "moving_average_window": self.sensor.moving_average_window,
            },
            "mqtt": {
                "enabled": self.mqtt.enabled,
                "broker_host": self.mqtt.broker_host,
                "broker_port": self.mqtt.broker_port,
                "telemetry_topic": self.mqtt.telemetry_topic,
                "alerts_topic": self.mqtt.alerts_topic,
            },
            "ml": {
                "enabled": self.ml.enabled,
                "contamination_rate": self.ml.contamination_rate,
            }
        }


# Singleton configuration instance
settings = SystemConfig()
