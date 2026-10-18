"""
Gas Sensor Model and Sensor Health Monitoring.
Simulates an MQ-series semiconductor gas sensor (e.g. MQ-5 / MQ-6)
with Exponential Moving Average (EMA) filtering and physical fault detection.
"""

from __future__ import annotations
import math
import time
from collections import deque
from typing import Optional, Tuple, Deque
from backend.config import settings
from backend.models import SensorHealthStatus


class SensorHealthMonitor:
    """
    Monitors sensor health and data plausibility:
    - Missing / timeout readings
    - Impossible / out-of-range values
    - Stuck sensor values (loss of natural analog variance)
    - Sudden unrealistic jumps (discontinuous spikes)
    """

    def __init__(
        self,
        min_ppm: float = settings.sensor.min_ppm,
        max_ppm: float = settings.sensor.max_ppm,
        max_jump_per_sec: float = settings.sensor.max_jump_per_sec,
        stuck_reading_count: int = settings.sensor.stuck_reading_count,
        timeout_seconds: float = settings.sensor.timeout_seconds,
    ):
        self.min_ppm = min_ppm
        self.max_ppm = max_ppm
        self.max_jump_per_sec = max_jump_per_sec
        self.stuck_reading_count = stuck_reading_count
        self.timeout_seconds = timeout_seconds

        self._last_reading: Optional[float] = None
        self._last_timestamp: float = time.time()
        self._recent_readings: Deque[float] = deque(maxlen=stuck_reading_count)
        self._current_status: SensorHealthStatus = SensorHealthStatus.NORMAL
        self._diagnostic_message: str = "Sensor operating nominally"

    def check(self, raw_value: Optional[float], current_time: Optional[float] = None) -> Tuple[SensorHealthStatus, str]:
        """
        Evaluate a new raw reading against physical plausibility criteria.
        Returns: (SensorHealthStatus, diagnostic_message)
        """
        now = current_time if current_time is not None else time.time()
        time_diff = max(0.001, now - self._last_timestamp)

        # 1. Check for Missing / Timeout / None reading
        if raw_value is None or math.isnan(raw_value):
            self._current_status = SensorHealthStatus.FAULT
            self._diagnostic_message = "FAULT: Missing or null sensor reading detected (communication timeout/loss)."
            self._last_timestamp = now
            return self._current_status, self._diagnostic_message

        # Check timeout if elapsed time is abnormally high
        if self._last_reading is not None and time_diff > self.timeout_seconds:
            self._current_status = SensorHealthStatus.FAULT
            self._diagnostic_message = f"FAULT: Sensor communication timeout ({time_diff:.1f}s > {self.timeout_seconds:.1f}s)."
            self._last_timestamp = now
            return self._current_status, self._diagnostic_message

        # 2. Check for Impossible / Out-of-Range values
        if raw_value < self.min_ppm:
            self._current_status = SensorHealthStatus.FAULT
            self._diagnostic_message = f"FAULT: Negative or sub-zero reading ({raw_value:.1f} ppm < {self.min_ppm} ppm)."
            self._last_reading = raw_value
            self._last_timestamp = now
            return self._current_status, self._diagnostic_message

        if raw_value > self.max_ppm:
            self._current_status = SensorHealthStatus.FAULT
            self._diagnostic_message = f"FAULT: Value exceeds sensor maximum operational range ({raw_value:.1f} ppm > {self.max_ppm} ppm)."
            self._last_reading = raw_value
            self._last_timestamp = now
            return self._current_status, self._diagnostic_message

        # 3. Check for Sudden Unrealistic Jumps
        if self._last_reading is not None:
            jump = abs(raw_value - self._last_reading)
            jump_rate = jump / time_diff
            if jump_rate > self.max_jump_per_sec:
                self._current_status = SensorHealthStatus.FAULT
                self._diagnostic_message = (
                    f"FAULT: Physically impossible jump detected "
                    f"({jump:.1f} ppm change in {time_diff:.2f}s = {jump_rate:.1f} ppm/s > {self.max_jump_per_sec} ppm/s limit)."
                )
                self._last_reading = raw_value
                self._last_timestamp = now
                self._recent_readings.append(raw_value)
                return self._current_status, self._diagnostic_message

        # 4. Check for Stuck Sensor Values (loss of analog noise)
        self._recent_readings.append(raw_value)
        if len(self._recent_readings) >= self.stuck_reading_count:
            # If all values in the queue are strictly identical to 3 decimal places
            first_val = self._recent_readings[0]
            all_identical = all(abs(v - first_val) < 1e-4 for v in self._recent_readings)
            if all_identical:
                self._current_status = SensorHealthStatus.WARNING
                self._diagnostic_message = (
                    f"WARNING: Sensor values appear stuck at {first_val:.1f} ppm "
                    f"for {self.stuck_reading_count} consecutive samples."
                )
                self._last_reading = raw_value
                self._last_timestamp = now
                return self._current_status, self._diagnostic_message

        # Normal condition
        self._current_status = SensorHealthStatus.NORMAL
        self._diagnostic_message = "Sensor operating nominally"
        self._last_reading = raw_value
        self._last_timestamp = now
        return self._current_status, self._diagnostic_message

    def reset(self) -> None:
        """Reset fault state tracker."""
        self._last_reading = None
        self._last_timestamp = time.time()
        self._recent_readings.clear()
        self._current_status = SensorHealthStatus.NORMAL
        self._diagnostic_message = "Sensor operating nominally"


class GasSensorModel:
    """
    Gas sensor signal processing module.
    Maintains raw readings, Exponential Moving Average (EMA) and Simple Moving Average (SMA).
    """

    def __init__(
        self,
        ema_alpha: float = settings.sensor.ema_alpha,
        sma_window: int = settings.sensor.moving_average_window,
    ):
        self.ema_alpha = max(0.01, min(1.0, ema_alpha))
        self.sma_window = max(1, sma_window)
        self._sma_buffer: Deque[float] = deque(maxlen=self.sma_window)
        self._ema_filtered: Optional[float] = None
        self._last_raw: Optional[float] = None
        self._last_timestamp: Optional[float] = None

    def process_reading(
        self,
        raw_gas: float,
        timestamp: Optional[float] = None
    ) -> Tuple[float, float, float]:
        """
        Process a new gas reading.
        Returns:
            (filtered_gas, rate_of_change, rate_per_second)
        """
        now = timestamp if timestamp is not None else time.time()
        
        # Calculate Rate of Change & Rate Per Second
        if self._last_raw is not None and self._last_timestamp is not None:
            time_diff = max(0.001, now - self._last_timestamp)
            rate_of_change = raw_gas - self._last_raw
            rate_per_second = rate_of_change / time_diff
        else:
            rate_of_change = 0.0
            rate_per_second = 0.0

        # Update EMA filter
        if self._ema_filtered is None:
            self._ema_filtered = raw_gas
        else:
            self._ema_filtered = (self.ema_alpha * raw_gas) + ((1.0 - self.ema_alpha) * self._ema_filtered)

        # Update SMA buffer
        self._sma_buffer.append(raw_gas)

        self._last_raw = raw_gas
        self._last_timestamp = now

        return round(self._ema_filtered, 2), round(rate_of_change, 2), round(rate_per_second, 2)

    def reset(self) -> None:
        """Reset internal filter states."""
        self._ema_filtered = None
        self._last_raw = None
        self._last_timestamp = None
        self._sma_buffer.clear()
