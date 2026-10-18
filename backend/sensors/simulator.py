"""
Sensor Simulator for Smart LPG Leak Detection System.
Generates realistic gas concentrations, environmental parameters (temp, humidity),
and supports configurable operational scenarios.
"""

from __future__ import annotations
import random
import time
from typing import Optional, Dict, Any
from backend.config import settings
from backend.models import SimulationScenario


class SensorSimulator:
    """
    Simulates MQ-series sensor readings and environmental conditions.
    Supports 7 distinct testing scenarios.
    """

    def __init__(
        self,
        initial_scenario: SimulationScenario = SimulationScenario.NORMAL,
        baseline_ppm: float = 60.0
    ):
        self.scenario = initial_scenario
        self.baseline_ppm = baseline_ppm
        self.current_gas = baseline_ppm
        self.temperature = 24.5
        self.humidity = 52.0
        
        # Scenario progression state
        self._step_counter = 0
        self._failure_cycle = 0
        self._is_running = True
        self._last_tick_time = time.time()

    def set_scenario(self, scenario: SimulationScenario) -> None:
        """Switch operational scenario and reset scenario counter."""
        self.scenario = scenario
        self._step_counter = 0
        
        # Specific scenario initial setups
        if scenario == SimulationScenario.NORMAL:
            self.current_gas = self.baseline_ppm + random.uniform(-5.0, 5.0)
        elif scenario == SimulationScenario.SLOW_LEAK:
            self.current_gas = max(self.baseline_ppm, self.current_gas)
        elif scenario == SimulationScenario.SUDDEN_LEAK:
            self.current_gas = max(100.0, self.current_gas)
        elif scenario == SimulationScenario.RAPID_SPIKE:
            self.current_gas = 120.0
        elif scenario == SimulationScenario.NOISY_SENSOR:
            self.current_gas = 150.0
        elif scenario == SimulationScenario.SENSOR_RECOVERY:
            # Start from high gas if it's currently low
            if self.current_gas < 350.0:
                self.current_gas = 450.0
        elif scenario == SimulationScenario.SENSOR_FAILURE:
            self._failure_cycle = 0

    def generate_reading(self) -> Dict[str, Any]:
        """
        Generate the next simulated sensor tick.
        Returns dictionary with raw_gas (or None/impossible value), temperature, humidity, timestamp.
        """
        self._step_counter += 1
        now = time.time()
        self._last_tick_time = now

        # Environmental background drift (slight natural fluctuations)
        self.temperature = round(24.0 + random.uniform(-1.0, 1.0) + (self.current_gas / 1000.0), 1)
        self.humidity = round(52.0 + random.uniform(-2.0, 2.0), 1)

        raw_gas: Optional[float] = None

        if self.scenario == SimulationScenario.NORMAL:
            # Baseline clean air with normal minor sensor noise (±3 ppm)
            noise = random.gauss(0, 2.5)
            self.current_gas = max(20.0, min(120.0, self.baseline_ppm + noise))
            raw_gas = round(self.current_gas, 2)

        elif self.scenario == SimulationScenario.SLOW_LEAK:
            # Steady continuous ramp up (+8 to +14 ppm per tick)
            ramp = random.uniform(8.0, 14.0)
            self.current_gas = min(650.0, self.current_gas + ramp)
            noise = random.gauss(0, 2.0)
            raw_gas = round(max(0.0, self.current_gas + noise), 2)

        elif self.scenario == SimulationScenario.SUDDEN_LEAK:
            # Aggressive rise (+60 to +90 ppm per tick)
            ramp = random.uniform(60.0, 95.0)
            self.current_gas = min(900.0, self.current_gas + ramp)
            noise = random.gauss(0, 3.0)
            raw_gas = round(self.current_gas + noise, 2)

        elif self.scenario == SimulationScenario.RAPID_SPIKE:
            # Step 1-2: sudden extreme surge (+180 to +240 ppm/s)
            if self._step_counter <= 2:
                self.current_gas += random.uniform(180.0, 240.0)
            else:
                # Levels off at a high plateau
                self.current_gas = min(850.0, self.current_gas + random.uniform(5.0, 15.0))
            noise = random.gauss(0, 2.0)
            raw_gas = round(self.current_gas + noise, 2)

        elif self.scenario == SimulationScenario.NOISY_SENSOR:
            # High noise jitter (±45 to ±70 ppm) on a mid-level baseline (150 ppm)
            jitter = random.gauss(0, 35.0)
            raw_gas = round(max(10.0, 150.0 + jitter), 2)
            self.current_gas = 150.0

        elif self.scenario == SimulationScenario.SENSOR_RECOVERY:
            # Gas dissipating after valve shutoff or ventilation (-25 to -40 ppm/tick)
            decay = random.uniform(25.0, 40.0)
            self.current_gas = max(self.baseline_ppm, self.current_gas - decay)
            noise = random.gauss(0, 2.0)
            raw_gas = round(max(20.0, self.current_gas + noise), 2)

        elif self.scenario == SimulationScenario.SENSOR_FAILURE:
            # Cycle through fault patterns
            self._failure_cycle += 1
            if self._failure_cycle in (1, 2):
                # Pattern A: Impossible negative value
                raw_gas = -55.0
            elif self._failure_cycle in (3, 4):
                # Pattern B: Disconnected / Missing (None)
                raw_gas = None
            elif self._failure_cycle in (5, 6):
                # Pattern C: Exceeds physical sensor max (2800 ppm > 2500 ppm limit)
                raw_gas = 2850.0
            elif self._failure_cycle in (7, 8):
                # Pattern D: Unrealistic jump (> 450 ppm jump in 1 second)
                raw_gas = 1200.0
            else:
                # Pattern E: Stuck value (repeated exact float)
                raw_gas = 123.456

        return {
            "timestamp": now,
            "raw_gas": raw_gas,
            "temperature": self.temperature,
            "humidity": self.humidity,
            "scenario": self.scenario.value
        }

    def start(self) -> None:
        self._is_running = True

    def stop(self) -> None:
        self._is_running = False

    @property
    def is_running(self) -> bool:
        return self._is_running

    def reset(self) -> None:
        """Reset simulator to normal baseline."""
        self.scenario = SimulationScenario.NORMAL
        self.current_gas = self.baseline_ppm
        self._step_counter = 0
        self._failure_cycle = 0
        self.temperature = 24.5
        self.humidity = 52.0

