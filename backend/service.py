"""
Core Service Coordinator for Smart LPG Safety System.
Glues together sensor simulation, signal filtering, plausibility monitoring,
deterministic risk evaluation, valve control, alert management, ML anomaly detection,
and persistent SQLite logging.
"""

from __future__ import annotations
import threading
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

from backend.config import settings
from backend.database import db
from backend.models import (
    RiskLevel,
    ValveState,
    ValveActionSource,
    SensorHealthStatus,
    SimulationScenario,
    EventType,
    SystemStatusResponse,
)
from backend.sensors.gas_sensor import GasSensorModel, SensorHealthMonitor
from backend.sensors.simulator import SensorSimulator
from backend.safety.risk_engine import RiskEngine
from backend.safety.valve_controller import ValveController
from backend.safety.alert_manager import AlertManager
from backend.ml.anomaly_detector import anomaly_detector
from backend.mqtt_client import mqtt_handler


class LPGSystemCoordinator:
    """
    Central orchestration service managing the end-to-end safety lifecycle.
    Runs an asynchronous/threaded background simulation loop.
    """

    def __init__(self):
        self.simulator = SensorSimulator(
            initial_scenario=SimulationScenario(settings.default_scenario)
        )
        self.sensor_model = GasSensorModel(
            ema_alpha=settings.sensor.ema_alpha,
            sma_window=settings.sensor.moving_average_window
        )
        self.health_monitor = SensorHealthMonitor(
            min_ppm=settings.sensor.min_ppm,
            max_ppm=settings.sensor.max_ppm,
            max_jump_per_sec=settings.sensor.max_jump_per_sec,
            stuck_reading_count=settings.sensor.stuck_reading_count,
            timeout_seconds=settings.sensor.timeout_seconds
        )
        self.risk_engine = RiskEngine(settings.safety)
        self.valve_controller = ValveController()
        self.alert_manager = AlertManager()

        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._simulation_running = True

        # State cache for immediate API response
        self._last_status: Dict[str, Any] = {}
        self._last_fault_logged_time: float = 0.0
        self._last_sensor_status: SensorHealthStatus = SensorHealthStatus.NORMAL

        # Perform initial tick
        self.tick()

    def tick(self) -> Dict[str, Any]:
        """
        Execute one complete iteration of the safety monitoring cycle.
        """
        with self._lock:
            # 1. Generate simulated sensor readings
            raw_sample = self.simulator.generate_reading()
            raw_gas = raw_sample["raw_gas"]
            temp = raw_sample["temperature"]
            hum = raw_sample["humidity"]
            now_iso = datetime.now(timezone.utc).isoformat()
            now_ts = raw_sample["timestamp"]

            # 2. Sensor Health & Plausibility Validation
            sensor_health, health_diag = self.health_monitor.check(raw_gas, current_time=now_ts)

            # Log sensor fault transitions (rate-limited)
            if sensor_health == SensorHealthStatus.FAULT:
                if self._last_sensor_status != SensorHealthStatus.FAULT or (time.time() - self._last_fault_logged_time > 10.0):
                    db.log_event(
                        event_type=EventType.SENSOR_FAULT.value,
                        gas_value=0.0 if raw_gas is None else round(raw_gas, 2),
                        risk_level=self.risk_engine.current_risk.value,
                        valve_state=self.valve_controller.state.value,
                        description=health_diag
                    )
                    self._last_fault_logged_time = time.time()
            elif self._last_sensor_status == SensorHealthStatus.FAULT and sensor_health == SensorHealthStatus.NORMAL:
                db.log_event(
                    event_type=EventType.SENSOR_RECOVERY.value,
                    gas_value=0.0 if raw_gas is None else round(raw_gas, 2),
                    risk_level=self.risk_engine.current_risk.value,
                    valve_state=self.valve_controller.state.value,
                    description="Sensor health restored to NORMAL operational status."
                )
            self._last_sensor_status = sensor_health

            # 3. Gas Signal Filtering
            if raw_gas is not None and sensor_health != SensorHealthStatus.FAULT:
                filtered_gas, roc, roc_per_sec = self.sensor_model.process_reading(raw_gas, timestamp=now_ts)
            else:
                # Use fallback/last known filtered reading or baseline
                filtered_gas = self.sensor_model._ema_filtered or settings.sensor.min_ppm
                roc = 0.0
                roc_per_sec = 0.0

            # 4. Machine Learning Anomaly Detection (Advisory)
            # ML analyzes multivariate patterns [gas, rate, temp, humidity]
            is_anomaly, anomaly_score, anomaly_label = anomaly_detector.predict(
                gas_ppm=filtered_gas,
                rate_per_sec=roc_per_sec,
                temp_c=temp,
                humidity_pct=hum
            )

            # 5. Deterministic Risk Classification & Rate-of-Rise Detection
            # Deterministic safety system ALWAYS has absolute authority!
            risk_level, rapid_rise, risk_reason = self.risk_engine.evaluate(
                filtered_gas=filtered_gas,
                rate_per_second=roc_per_sec,
                sensor_status=sensor_health
            )

            # 6. Valve Controller State Update
            valve_state, valve_changed, valve_msg = self.valve_controller.update_from_risk(risk_level)
            if valve_changed and valve_state in (ValveState.CLOSING, ValveState.CLOSED):
                db.log_event(
                    event_type=EventType.AUTOMATIC_SHUTOFF.value,
                    gas_value=round(filtered_gas, 2),
                    risk_level=risk_level.value,
                    valve_state=valve_state.value,
                    description=f"{valve_msg} (Gas: {filtered_gas:.1f} ppm, RoR: {roc_per_sec:+.1f} ppm/s)"
                )

            # 7. Multi-Level Alert Escalation & Logging
            alerts = self.alert_manager.update_alerts(
                risk_level=risk_level,
                rapid_rise=rapid_rise,
                current_gas=filtered_gas,
                valve_state=valve_state,
                reason=risk_reason
            )

            # 8. Persist Telemetry to Database
            db.log_reading(
                raw_gas=0.0 if raw_gas is None else round(raw_gas, 2),
                filtered_gas=round(filtered_gas, 2),
                rate_of_change=round(roc, 2),
                rate_per_second=round(roc_per_sec, 2),
                temperature=temp,
                humidity=hum,
                sensor_status=sensor_health.value,
                is_anomaly=is_anomaly,
                anomaly_score=anomaly_score,
                timestamp=now_iso
            )

            # 9. Cache Current Status
            snapshot = {
                "timestamp": now_iso,
                "risk_level": risk_level.value,
                "raw_gas": 0.0 if raw_gas is None else round(raw_gas, 2),
                "filtered_gas": round(filtered_gas, 2),
                "rate_of_change": round(roc, 2),
                "rate_per_second": round(roc_per_sec, 2),
                "rapid_rise_detected": rapid_rise,
                "temperature": temp,
                "humidity": hum,
                "valve_state": valve_state.value,
                "valve_angle_deg": self.valve_controller.servo_angle_deg,
                "valve_last_source": self.valve_controller.last_action_source.value,
                "sensor_health": sensor_health.value,
                "sensor_health_reason": health_diag,
                "buzzer_state": alerts["buzzer_state"],
                "warning_led": alerts["warning_led"],
                "danger_led": alerts["danger_led"],
                "simulation_running": self._simulation_running,
                "active_scenario": self.simulator.scenario.value,
                "is_anomaly": is_anomaly,
                "anomaly_label": anomaly_label,
                "thresholds": {
                    "safe_max": settings.safety.safe_max,
                    "warning_threshold": settings.safety.warning_threshold,
                    "danger_threshold": settings.safety.danger_threshold,
                    "critical_threshold": settings.safety.critical_threshold,
                    "rate_of_rise_threshold": settings.safety.rate_of_rise_threshold,
                    "hysteresis_ppm": settings.safety.hysteresis_ppm,
                }
            }
            self._last_status = snapshot

            # 10. Optional MQTT Telemetry Publish
            mqtt_handler.publish_telemetry(snapshot)
            if risk_level in (RiskLevel.DANGER, RiskLevel.CRITICAL) or rapid_rise:
                mqtt_handler.publish_alert({
                    "event": "SAFETY_ALARM",
                    "risk_level": risk_level.value,
                    "gas_ppm": round(filtered_gas, 2),
                    "valve_state": valve_state.value,
                    "timestamp": now_iso
                })

            return snapshot

    def start_background_loop(self) -> None:
        """Launch the continuous background simulation worker."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop_background_loop(self) -> None:
        """Halt the continuous background simulation worker."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            if self._simulation_running:
                try:
                    self.tick()
                except Exception as e:
                    # Defensive: avoid loop crash
                    pass
            self._stop_event.wait(timeout=settings.simulation_interval_sec)

    # --------------------------------------------------------------------------
    # Control API Handlers
    # --------------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Return the latest cached status snapshot."""
        with self._lock:
            return dict(self._last_status)

    def set_scenario(self, scenario: SimulationScenario) -> None:
        """Switch operational testing scenario."""
        with self._lock:
            self.simulator.set_scenario(scenario)
            if scenario in (SimulationScenario.NORMAL, SimulationScenario.SENSOR_RECOVERY):
                self.sensor_model._ema_filtered = self.simulator.current_gas
                self.sensor_model._last_raw = self.simulator.current_gas
            db.log_event(
                event_type=EventType.SCENARIO_CHANGED.value,
                gas_value=self.simulator.current_gas,
                risk_level=self.risk_engine.current_risk.value,
                valve_state=self.valve_controller.state.value,
                description=f"Simulation scenario changed to {scenario.value}"
            )

    def start_simulation(self) -> None:
        with self._lock:
            self._simulation_running = True
            self.simulator.start()
            db.log_event(
                event_type=EventType.SIMULATION_STARTED.value,
                gas_value=self.simulator.current_gas,
                risk_level=self.risk_engine.current_risk.value,
                valve_state=self.valve_controller.state.value,
                description="Simulation pipeline resumed"
            )

    def stop_simulation(self) -> None:
        with self._lock:
            self._simulation_running = False
            self.simulator.stop()
            db.log_event(
                event_type=EventType.SIMULATION_STOPPED.value,
                gas_value=self.simulator.current_gas,
                risk_level=self.risk_engine.current_risk.value,
                valve_state=self.valve_controller.state.value,
                description="Simulation pipeline paused"
            )

    def manual_close_valve(self, confirmed: bool) -> Tuple[bool, str]:
        """Trigger manual valve closure override."""
        with self._lock:
            success, msg = self.valve_controller.manual_close(confirmed)
            if success:
                db.log_event(
                    event_type=EventType.MANUAL_SHUTOFF.value,
                    gas_value=self._last_status.get("filtered_gas", 0.0),
                    risk_level=self.risk_engine.current_risk.value,
                    valve_state=self.valve_controller.state.value,
                    description=msg
                )
            return success, msg

    def manual_open_valve(self, confirmed: bool) -> Tuple[bool, str]:
        """Trigger manual valve open override."""
        with self._lock:
            success, msg = self.valve_controller.manual_open(confirmed, self.risk_engine.current_risk)
            if success:
                db.log_event(
                    event_type=EventType.MANUAL_OPEN.value,
                    gas_value=self._last_status.get("filtered_gas", 0.0),
                    risk_level=self.risk_engine.current_risk.value,
                    valve_state=self.valve_controller.state.value,
                    description=msg
                )
            return success, msg

    def reset_system(self, confirmed: bool) -> Tuple[bool, str]:
        """Reset safety lockout and clear faults if gas has cleared."""
        with self._lock:
            success, msg = self.valve_controller.reset_system(confirmed, self.risk_engine.current_risk)
            if success:
                self.risk_engine.reset()
                self.alert_manager.reset()
                self.health_monitor.reset()
                self.sensor_model.reset()
                db.log_event(
                    event_type=EventType.VALVE_RESET.value,
                    gas_value=self._last_status.get("filtered_gas", 0.0),
                    risk_level=RiskLevel.SAFE.value,
                    valve_state=ValveState.OPEN.value,
                    description=msg
                )
            return success, msg


# Global singleton instance
coordinator = LPGSystemCoordinator()
