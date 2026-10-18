"""
Alert and Multi-Level Escalation Manager.
Coordinates visual indicators (Warning LED, Danger LED), acoustic alerts (simulated buzzer),
system event logging, and telemetry dispatch.
"""

from __future__ import annotations
import time
from typing import Dict, Any, Optional
from backend.models import RiskLevel, EventType, ValveState
from backend.database import db


class AlertManager:
    """
    Manages escalating alert outputs:
    - buzzer_state: 'OFF', 'BEEPING', 'CONTINUOUS'
    - warning_led: bool
    - danger_led: bool
    - persistent event logging
    """

    def __init__(self):
        self.buzzer_state: str = "OFF"
        self.warning_led: bool = False
        self.danger_led: bool = False
        self.last_logged_risk: Optional[RiskLevel] = None
        self.last_rapid_rise_time: float = 0.0

    def update_alerts(
        self,
        risk_level: RiskLevel,
        rapid_rise: bool,
        current_gas: float,
        valve_state: ValveState,
        reason: str
    ) -> Dict[str, Any]:
        """
        Update alert peripherals and log critical safety transitions.
        """
        now = time.time()

        # Update actuator/annunciator states based on risk hierarchy
        if risk_level == RiskLevel.SAFE:
            self.buzzer_state = "OFF"
            self.warning_led = False
            self.danger_led = False

        elif risk_level == RiskLevel.WARNING:
            self.buzzer_state = "OFF"
            self.warning_led = True
            self.danger_led = False

        elif risk_level == RiskLevel.DANGER:
            self.buzzer_state = "BEEPING"
            self.warning_led = True
            self.danger_led = True

        elif risk_level == RiskLevel.CRITICAL:
            self.buzzer_state = "CONTINUOUS"
            self.warning_led = True
            self.danger_led = True

        # Rapid gas rise triggers immediate buzzer alert even if in WARNING
        if rapid_rise and self.buzzer_state == "OFF":
            self.buzzer_state = "BEEPING"
            self.danger_led = True

        # Event Logging: Log on risk level transitions
        if self.last_logged_risk != risk_level:
            event_type = f"GAS_{risk_level.value}"
            db.log_event(
                event_type=event_type,
                gas_value=round(current_gas, 2),
                risk_level=risk_level.value,
                valve_state=valve_state.value,
                description=f"Risk level transitioned to {risk_level.value}: {reason}"
            )
            self.last_logged_risk = risk_level

        # Event Logging: Rapid rise event (rate-limited to once per 5 seconds to avoid flooding)
        if rapid_rise and (now - self.last_rapid_rise_time > 5.0):
            db.log_event(
                event_type=EventType.RAPID_GAS_RISE.value,
                gas_value=round(current_gas, 2),
                risk_level=risk_level.value,
                valve_state=valve_state.value,
                description=f"Rapid gas rise surge detected: {reason}"
            )
            self.last_rapid_rise_time = now

        return {
            "buzzer_state": self.buzzer_state,
            "warning_led": self.warning_led,
            "danger_led": self.danger_led
        }

    def reset(self) -> None:
        """Reset alert peripherals to SAFE."""
        self.buzzer_state = "OFF"
        self.warning_led = False
        self.danger_led = False
        self.last_logged_risk = None
        self.last_rapid_rise_time = 0.0

