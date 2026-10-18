"""
Unit tests for Gas Sensor Model, Sensor Health Monitoring, and Simulator Scenarios.
"""

import math
import pytest
from backend.models import SensorHealthStatus, SimulationScenario
from backend.sensors.gas_sensor import GasSensorModel, SensorHealthMonitor
from backend.sensors.simulator import SensorSimulator


def test_sensor_ema_filtering():
    """Verify Exponential Moving Average (EMA) smooths noisy fluctuations."""
    sensor = GasSensorModel(ema_alpha=0.25)
    
    # First reading initializes filter
    filtered, roc, rps = sensor.process_reading(100.0, timestamp=1000.0)
    assert filtered == 100.0
    assert roc == 0.0

    # Sudden jump to 200.0 at t=1001.0
    filtered2, roc2, rps2 = sensor.process_reading(200.0, timestamp=1001.0)
    # EMA: 0.25 * 200 + 0.75 * 100 = 50 + 75 = 125.0
    assert filtered2 == 125.0
    assert roc2 == 100.0
    assert rps2 == 100.0


def test_health_monitor_normal_readings():
    """Verify valid readings produce NORMAL status."""
    monitor = SensorHealthMonitor(min_ppm=0.0, max_ppm=2500.0, max_jump_per_sec=350.0)
    status, msg = monitor.check(65.4, current_time=100.0)
    assert status == SensorHealthStatus.NORMAL
    assert "nominally" in msg


def test_health_monitor_missing_or_nan():
    """Verify None or NaN readings trigger FAULT."""
    monitor = SensorHealthMonitor()
    
    status, msg = monitor.check(None, current_time=100.0)
    assert status == SensorHealthStatus.FAULT
    assert "Missing or null" in msg

    status, msg = monitor.check(float("nan"), current_time=101.0)
    assert status == SensorHealthStatus.FAULT
    assert "Missing or null" in msg


def test_health_monitor_out_of_range():
    """Verify values outside plausible physical range trigger FAULT."""
    monitor = SensorHealthMonitor(min_ppm=0.0, max_ppm=2500.0)
    
    # Negative ppm
    status, msg = monitor.check(-15.0, current_time=100.0)
    assert status == SensorHealthStatus.FAULT
    assert "Negative or sub-zero" in msg

    # Exceeding maximum sensor limit
    status, msg = monitor.check(3000.0, current_time=101.0)
    assert status == SensorHealthStatus.FAULT
    assert "exceeds sensor maximum" in msg


def test_health_monitor_unrealistic_jump():
    """Verify sudden physically impossible rate of rise triggers FAULT."""
    monitor = SensorHealthMonitor(max_jump_per_sec=350.0)
    
    # Initial baseline
    monitor.check(50.0, current_time=100.0)

    # Jump of 500 ppm in 1.0 second (500 ppm/s > 350 ppm/s)
    status, msg = monitor.check(550.0, current_time=101.0)
    assert status == SensorHealthStatus.FAULT
    assert "impossible jump" in msg


def test_health_monitor_stuck_sensor():
    """Verify frozen/stuck reading across N samples triggers WARNING."""
    monitor = SensorHealthMonitor(stuck_reading_count=5)
    
    # Feed 5 identical readings
    for i in range(5):
        status, msg = monitor.check(120.0, current_time=100.0 + i)

    assert status == SensorHealthStatus.WARNING
    assert "stuck" in msg


def test_health_monitor_timeout():
    """Verify communication delay exceeding threshold triggers FAULT."""
    monitor = SensorHealthMonitor(timeout_seconds=5.0)
    
    monitor.check(50.0, current_time=100.0)
    # 7 seconds later
    status, msg = monitor.check(52.0, current_time=107.0)
    assert status == SensorHealthStatus.FAULT
    assert "timeout" in msg


def test_simulator_scenarios():
    """Verify simulator generates appropriate outputs across scenarios."""
    sim = SensorSimulator(initial_scenario=SimulationScenario.NORMAL, baseline_ppm=60.0)
    
    # Normal scenario
    sample = sim.generate_reading()
    assert 20.0 <= sample["raw_gas"] <= 120.0

    # Slow leak scenario
    sim.set_scenario(SimulationScenario.SLOW_LEAK)
    sample1 = sim.generate_reading()
    sample2 = sim.generate_reading()
    assert sample2["raw_gas"] >= sample1["raw_gas"] - 5.0  # Overall trending up

    # Rapid spike scenario
    sim.set_scenario(SimulationScenario.RAPID_SPIKE)
    spike_sample = sim.generate_reading()
    assert spike_sample["raw_gas"] > 250.0

    # Sensor recovery scenario
    sim.set_scenario(SimulationScenario.SENSOR_RECOVERY)
    sim.current_gas = 500.0
    rec_sample1 = sim.generate_reading()
    rec_sample2 = sim.generate_reading()
    assert rec_sample2["raw_gas"] < rec_sample1["raw_gas"]
