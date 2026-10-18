"""
Simulated Servo Valve Actuator and Shut-Off Controller.
Implements industrial safety shut-off logic, transition dynamics (servo angle),
safety lockout hysteresis, and confirmed manual override controls.
"""

from __future__ import annotations
import time
from typing import Tuple, Optional
from backend.models import ValveState, ValveActionSource, RiskLevel


class ValveController:
    """
    Manages the state and simulated physical actuator (servo motor)
    for the gas safety shut-off valve.
    
    Servo Actuator mapping:
        - 90.0 degrees = Fully OPEN (gas flows normally)
        - 45.0 degrees = In transition / CLOSING
        - 0.0 degrees  = Fully CLOSED (gas supply isolated)
    """

    def __init__(self):
        self.state: ValveState = ValveState.OPEN
        self.servo_angle_deg: float = 90.0
        self.last_action_source: ValveActionSource = ValveActionSource.SYSTEM_RESET
        self.last_action_timestamp: float = time.time()
        self.last_action_description: str = "System initialized; valve OPEN"
        
        # Safety lockout: once automatically shut off, valve latches shut
        # until explicitly reset or safe conditions are certified
        self._safety_lockout: bool = False

    def update_from_risk(self, risk_level: RiskLevel) -> Tuple[ValveState, bool, str]:
        """
        Evaluate automatic safety shut-off rule.
        Returns:
            (ValveState, changed: bool, message: str)
        """
        now = time.time()
        prev_state = self.state

        # CRITICAL condition: Immediate full shut-off
        if risk_level == RiskLevel.CRITICAL:
            self.state = ValveState.CLOSED
            self.servo_angle_deg = 0.0
            self.last_action_source = ValveActionSource.AUTOMATIC_RULE
            self.last_action_timestamp = now
            self._safety_lockout = True
            msg = "AUTOMATIC SHUT-OFF: Emergency isolation activated due to CRITICAL gas level"
            self.last_action_description = msg
            return self.state, (prev_state != ValveState.CLOSED), msg

        # DANGER condition: Valve begins rapid closure
        elif risk_level == RiskLevel.DANGER:
            if self.state == ValveState.OPEN:
                self.state = ValveState.CLOSING
                self.servo_angle_deg = 45.0
                self.last_action_source = ValveActionSource.AUTOMATIC_RULE
                self.last_action_timestamp = now
                self._safety_lockout = True
                msg = "AUTOMATIC SHUT-OFF: Actuator triggered into CLOSING state due to DANGER gas level"
                self.last_action_description = msg
                return self.state, True, msg
            elif self.state == ValveState.CLOSING:
                # Progress closure to fully closed
                self.state = ValveState.CLOSED
                self.servo_angle_deg = 0.0
                msg = "AUTOMATIC SHUT-OFF: Actuator completed closure; gas isolated"
                self.last_action_description = msg
                return self.state, (prev_state != ValveState.CLOSED), msg

        # WARNING condition: Valve remains in current state (does not auto-close, but alerts)
        elif risk_level == RiskLevel.WARNING:
            # If already locked out by previous Danger/Critical, stay closed!
            if self._safety_lockout:
                return self.state, False, "Valve remains locked CLOSED following safety event (WARNING active)"
            return self.state, False, "Valve OPEN; warning status active"

        # SAFE condition: Valve remains open, or remains locked until reset
        elif risk_level == RiskLevel.SAFE:
            if self._safety_lockout:
                return self.state, False, "Valve latched CLOSED for safety; requires SYSTEM RESET to reopen"
            
            if self.state != ValveState.OPEN:
                # If not locked out and safe, return to open
                self.state = ValveState.OPEN
                self.servo_angle_deg = 90.0
                self.last_action_source = ValveActionSource.AUTOMATIC_RULE
                self.last_action_timestamp = now
                msg = "Valve returned to OPEN state under verified SAFE conditions"
                self.last_action_description = msg
                return self.state, (prev_state != ValveState.OPEN), msg

        return self.state, False, "Valve state unchanged"

    def manual_close(self, confirmed: bool) -> Tuple[bool, str]:
        """Manual emergency shut-off command."""
        if not confirmed:
            return False, "Manual valve closure rejected: UI confirmation required"

        prev_state = self.state
        self.state = ValveState.CLOSED
        self.servo_angle_deg = 0.0
        self.last_action_source = ValveActionSource.MANUAL_OVERRIDE
        self.last_action_timestamp = time.time()
        self.last_action_description = "Manually closed by operator override"
        self._safety_lockout = True
        return True, "Valve successfully CLOSED via manual operator override"

    def manual_open(self, confirmed: bool, current_risk: RiskLevel) -> Tuple[bool, str]:
        """Manual valve open command."""
        if not confirmed:
            return False, "Manual valve opening rejected: UI confirmation required"

        # Safety interlock: Prevent manual opening during active DANGER or CRITICAL
        if current_risk in (RiskLevel.DANGER, RiskLevel.CRITICAL):
            return False, f"Opening valve BLOCKED by safety interlock: current risk is {current_risk.value}"

        self.state = ValveState.OPEN
        self.servo_angle_deg = 90.0
        self.last_action_source = ValveActionSource.MANUAL_OVERRIDE
        self.last_action_timestamp = time.time()
        self.last_action_description = "Manually opened by operator override"
        self._safety_lockout = False
        return True, "Valve successfully OPENED via manual operator override"

    def reset_system(self, confirmed: bool, current_risk: RiskLevel) -> Tuple[bool, str]:
        """Reset safety lockout and restore valve to nominal state if safe."""
        if not confirmed:
            return False, "System reset rejected: UI confirmation required"

        if current_risk in (RiskLevel.DANGER, RiskLevel.CRITICAL):
            return False, f"System reset BLOCKED: environment remains hazardous ({current_risk.value})"

        self._safety_lockout = False
        self.state = ValveState.OPEN
        self.servo_angle_deg = 90.0
        self.last_action_source = ValveActionSource.SYSTEM_RESET
        self.last_action_timestamp = time.time()
        self.last_action_description = "Safety lockout cleared; system and valve reset to normal OPEN"
        return True, "Safety lockout successfully reset. Valve restored to OPEN"
