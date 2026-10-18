"""
Unit tests for Risk Classification and Rate-of-Rise (RoR) Detection Engine.
"""

import pytest
from backend.config import SafetyThresholds
from backend.models import RiskLevel, SensorHealthStatus
from backend.safety.risk_engine import RiskEngine


@pytest.fixture
def custom_thresholds():
    return SafetyThresholds(
        safe_max=199.0,
        warning_threshold=200.0,
        danger_threshold=400.0,
        critical_threshold=700.0,
        hysteresis_ppm=30.0,
        rate_of_rise_threshold=25.0
    )


@pytest.fixture
def engine(custom_thresholds):
    return RiskEngine(thresholds=custom_thresholds)


def test_safe_classification(engine):
    """Verify gas below warning threshold is classified as SAFE."""
    risk, rapid, reason = engine.evaluate(filtered_gas=120.0, rate_per_second=1.0)
    assert risk == RiskLevel.SAFE
    assert rapid is False
    assert "SAFE" in reason


def test_warning_classification(engine):
    """Verify gas reaching warning threshold is classified as WARNING."""
    risk, rapid, reason = engine.evaluate(filtered_gas=205.0, rate_per_second=2.0)
    assert risk == RiskLevel.WARNING
    assert rapid is False
    assert "WARNING" in reason


def test_danger_classification(engine):
    """Verify gas reaching danger threshold is classified as DANGER."""
    risk, rapid, reason = engine.evaluate(filtered_gas=410.0, rate_per_second=3.0)
    assert risk == RiskLevel.DANGER
    assert rapid is False
    assert "DANGER" in reason


def test_critical_classification(engine):
    """Verify gas reaching critical threshold is classified as CRITICAL."""
    risk, rapid, reason = engine.evaluate(filtered_gas=720.0, rate_per_second=4.0)
    assert risk == RiskLevel.CRITICAL
    assert rapid is False
    assert "CRITICAL" in reason


def test_rapid_rise_detection_escalates_to_danger(engine):
    """Verify rate-of-rise exceeding threshold triggers rapid rise and escalates SAFE to DANGER."""
    # Gas is low (100 ppm), but sudden burst of 30 ppm/s
    risk, rapid, reason = engine.evaluate(filtered_gas=100.0, rate_per_second=30.0)
    assert rapid is True
    assert risk == RiskLevel.DANGER
    assert "RAPID GAS RISE TRIGGER" in reason


def test_rapid_rise_escalates_danger_to_critical(engine):
    """Verify rapid rise while already at elevated gas escalates to CRITICAL."""
    # Gas is at 450 ppm (DANGER level) and spiking at +40 ppm/s
    # First set to DANGER
    engine.evaluate(filtered_gas=450.0, rate_per_second=5.0)
    assert engine.current_risk == RiskLevel.DANGER
    
    # Now trigger rapid spike
    risk, rapid, reason = engine.evaluate(filtered_gas=490.0, rate_per_second=40.0)
    assert rapid is True
    assert risk == RiskLevel.CRITICAL
    assert "CRITICAL SURGE" in reason


def test_hysteresis_warning_to_safe(engine):
    """
    Verify hysteresis prevents bouncing:
    Warning is at 200 ppm, hysteresis is 30 ppm.
    Must drop below (200 - 30) = 170 ppm to return to SAFE.
    """
    # 1. Trigger WARNING at 210 ppm
    risk, _, _ = engine.evaluate(filtered_gas=210.0, rate_per_second=0.0)
    assert risk == RiskLevel.WARNING

    # 2. Gas drops to 185 ppm (below 200, but still within hysteresis deadband > 170)
    risk, _, reason = engine.evaluate(filtered_gas=185.0, rate_per_second=-5.0)
    assert risk == RiskLevel.WARNING
    assert "hysteresis active" in reason

    # 3. Gas drops to 160 ppm (below 170 ppm clearing threshold)
    risk, _, reason = engine.evaluate(filtered_gas=160.0, rate_per_second=-5.0)
    assert risk == RiskLevel.SAFE
    assert "safe clearing limit" in reason


def test_hysteresis_danger_to_warning(engine):
    """
    Verify hysteresis from DANGER (400 ppm threshold, 30 ppm hysteresis):
    Must drop below 370 ppm to drop to WARNING.
    """
    engine.evaluate(filtered_gas=420.0, rate_per_second=0.0)
    assert engine.current_risk == RiskLevel.DANGER

    # Drops to 385 ppm (within hysteresis)
    risk, _, reason = engine.evaluate(filtered_gas=385.0, rate_per_second=-5.0)
    assert risk == RiskLevel.DANGER
    assert "hysteresis active" in reason

    # Drops to 360 ppm (below 370 ppm)
    risk, _, reason = engine.evaluate(filtered_gas=360.0, rate_per_second=-5.0)
    assert risk == RiskLevel.WARNING


def test_sensor_fault_elevates_risk(engine):
    """Verify sensor FAULT status results in safety alert elevation."""
    risk, rapid, reason = engine.evaluate(
        filtered_gas=50.0,
        rate_per_second=0.0,
        sensor_status=SensorHealthStatus.FAULT
    )
    assert risk == RiskLevel.WARNING
    assert "Sensor hardware fault" in reason
