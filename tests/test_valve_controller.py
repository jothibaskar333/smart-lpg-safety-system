"""
Unit tests for Valve Controller and Servo Actuator Logic.
"""

import pytest
from backend.models import ValveState, ValveActionSource, RiskLevel
from backend.safety.valve_controller import ValveController


@pytest.fixture
def valve():
    return ValveController()


def test_initial_valve_state(valve):
    """Verify initial state is OPEN at 90 degrees."""
    assert valve.state == ValveState.OPEN
    assert valve.servo_angle_deg == 90.0


def test_safe_and_warning_keep_valve_open(valve):
    """SAFE and WARNING risk levels keep valve open."""
    state, changed, _ = valve.update_from_risk(RiskLevel.SAFE)
    assert state == ValveState.OPEN
    assert not changed
    assert valve.servo_angle_deg == 90.0

    state, changed, _ = valve.update_from_risk(RiskLevel.WARNING)
    assert state == ValveState.OPEN
    assert not changed
    assert valve.servo_angle_deg == 90.0


def test_danger_transitions_to_closing_then_closed(valve):
    """DANGER risk level moves valve from OPEN -> CLOSING -> CLOSED."""
    # First tick in DANGER: starts closing
    state, changed, msg = valve.update_from_risk(RiskLevel.DANGER)
    assert state == ValveState.CLOSING
    assert changed is True
    assert valve.servo_angle_deg == 45.0
    assert "CLOSING" in msg

    # Second tick in DANGER: completes closure
    state, changed, msg = valve.update_from_risk(RiskLevel.DANGER)
    assert state == ValveState.CLOSED
    assert changed is True
    assert valve.servo_angle_deg == 0.0
    assert "completed closure" in msg


def test_critical_triggers_immediate_closed(valve):
    """CRITICAL risk level triggers direct closure."""
    state, changed, msg = valve.update_from_risk(RiskLevel.CRITICAL)
    assert state == ValveState.CLOSED
    assert changed is True
    assert valve.servo_angle_deg == 0.0
    assert "Emergency isolation" in msg


def test_lockout_hysteresis_prevents_auto_reopening(valve):
    """Once valve is automatically closed, returning to SAFE must NOT automatically reopen it."""
    # 1. Trigger shut-off via CRITICAL
    valve.update_from_risk(RiskLevel.CRITICAL)
    assert valve.state == ValveState.CLOSED

    # 2. Gas drops to SAFE
    state, changed, msg = valve.update_from_risk(RiskLevel.SAFE)
    assert state == ValveState.CLOSED
    assert changed is False
    assert "requires SYSTEM RESET" in msg

    # 3. Reset system allows reopening
    success, reset_msg = valve.reset_system(confirmed=True, current_risk=RiskLevel.SAFE)
    assert success is True
    assert valve.state == ValveState.OPEN
    assert valve.servo_angle_deg == 90.0


def test_manual_close_override(valve):
    """Manual close requires confirmation and transitions valve to CLOSED."""
    # Unconfirmed must fail
    success, msg = valve.manual_close(confirmed=False)
    assert success is False
    assert valve.state == ValveState.OPEN

    # Confirmed must succeed
    success, msg = valve.manual_close(confirmed=True)
    assert success is True
    assert valve.state == ValveState.CLOSED
    assert valve.servo_angle_deg == 0.0
    assert valve.last_action_source == ValveActionSource.MANUAL_OVERRIDE


def test_manual_open_interlock_during_danger(valve):
    """Manual open is blocked if current risk is DANGER or CRITICAL."""
    valve.state = ValveState.CLOSED

    # Attempt to open during DANGER
    success, msg = valve.manual_open(confirmed=True, current_risk=RiskLevel.DANGER)
    assert success is False
    assert valve.state == ValveState.CLOSED
    assert "BLOCKED by safety interlock" in msg

    # Attempt to open during SAFE
    success, msg = valve.manual_open(confirmed=True, current_risk=RiskLevel.SAFE)
    assert success is True
    assert valve.state == ValveState.OPEN
    assert valve.servo_angle_deg == 90.0


def test_system_reset_blocked_during_hazard(valve):
    """System reset cannot be performed while hazardous condition persists."""
    valve.state = ValveState.CLOSED
    valve._safety_lockout = True

    # Blocked during CRITICAL
    success, msg = valve.reset_system(confirmed=True, current_risk=RiskLevel.CRITICAL)
    assert success is False
    assert "BLOCKED" in msg

    # Allowed when SAFE
    success, msg = valve.reset_system(confirmed=True, current_risk=RiskLevel.SAFE)
    assert success is True
    assert valve.state == ValveState.OPEN

