"""
Risk Classification and Rate-of-Rise (RoR) Detection Engine.
Implements multi-level safety thresholds with hysteresis band protection
and abnormal rapid gas rise detection.
"""

from __future__ import annotations
from typing import Tuple, Optional
from backend.config import settings, SafetyThresholds
from backend.models import RiskLevel, SensorHealthStatus


class RiskEngine:
    """
    Evaluates filtered gas concentration and rate-of-rise to determine risk level.
    Uses configurable demonstration thresholds and hysteresis deadband.
    """

    def __init__(self, thresholds: Optional[SafetyThresholds] = None):
        self.thresholds = thresholds or settings.safety
        self.current_risk: RiskLevel = RiskLevel.SAFE
        self.last_rapid_rise: bool = False
        self.last_reason: str = "Nominal safe environment"

    def evaluate(
        self,
        filtered_gas: float,
        rate_per_second: float,
        sensor_status: SensorHealthStatus = SensorHealthStatus.NORMAL
    ) -> Tuple[RiskLevel, bool, str]:
        """
        Evaluate current risk level.
        Returns:
            (RiskLevel, rapid_rise_detected: bool, evaluation_reason: str)
        """
        # If the sensor is in FAULT, elevate risk to WARNING or DANGER depending on last known reading
        if sensor_status == SensorHealthStatus.FAULT:
            self.current_risk = RiskLevel.WARNING
            self.last_rapid_rise = False
            self.last_reason = "Sensor hardware fault or signal loss detected"
            return self.current_risk, False, self.last_reason

        # 1. Rate-of-Rise (RoR) Detection
        # Sudden gas increase indicates active rupture, line break, or rapid leak
        rapid_rise = rate_per_second >= self.thresholds.rate_of_rise_threshold
        self.last_rapid_rise = rapid_rise

        w_thresh = self.thresholds.warning_threshold
        d_thresh = self.thresholds.danger_threshold
        c_thresh = self.thresholds.critical_threshold
        hyst = self.thresholds.hysteresis_ppm

        new_risk = self.current_risk
        reason = "Gas within safe limits"

        # Determine target risk level based on concentration with hysteresis
        if self.current_risk == RiskLevel.SAFE:
            if filtered_gas >= c_thresh:
                new_risk = RiskLevel.CRITICAL
                reason = f"Gas concentration ({filtered_gas:.1f} ppm) exceeded CRITICAL threshold ({c_thresh:.1f} ppm)"
            elif filtered_gas >= d_thresh:
                new_risk = RiskLevel.DANGER
                reason = f"Gas concentration ({filtered_gas:.1f} ppm) exceeded DANGER threshold ({d_thresh:.1f} ppm)"
            elif filtered_gas >= w_thresh:
                new_risk = RiskLevel.WARNING
                reason = f"Gas concentration ({filtered_gas:.1f} ppm) exceeded WARNING threshold ({w_thresh:.1f} ppm)"
            else:
                new_risk = RiskLevel.SAFE
                reason = f"Gas concentration ({filtered_gas:.1f} ppm) is SAFE"

        elif self.current_risk == RiskLevel.WARNING:
            if filtered_gas >= c_thresh:
                new_risk = RiskLevel.CRITICAL
                reason = f"Gas concentration ({filtered_gas:.1f} ppm) escalated to CRITICAL threshold ({c_thresh:.1f} ppm)"
            elif filtered_gas >= d_thresh:
                new_risk = RiskLevel.DANGER
                reason = f"Gas concentration ({filtered_gas:.1f} ppm) escalated to DANGER threshold ({d_thresh:.1f} ppm)"
            elif filtered_gas < (w_thresh - hyst):
                # Hysteresis band check to transition back to SAFE
                new_risk = RiskLevel.SAFE
                reason = f"Gas concentration ({filtered_gas:.1f} ppm) dropped below safe clearing limit ({w_thresh - hyst:.1f} ppm)"
            else:
                # In hysteresis deadband, maintain WARNING
                new_risk = RiskLevel.WARNING
                reason = f"Gas concentration ({filtered_gas:.1f} ppm) maintaining WARNING state (hysteresis active)"

        elif self.current_risk == RiskLevel.DANGER:
            if filtered_gas >= c_thresh:
                new_risk = RiskLevel.CRITICAL
                reason = f"Gas concentration ({filtered_gas:.1f} ppm) escalated to CRITICAL threshold ({c_thresh:.1f} ppm)"
            elif filtered_gas < (d_thresh - hyst):
                # Dropped below danger hysteresis boundary
                if filtered_gas < (w_thresh - hyst):
                    new_risk = RiskLevel.SAFE
                    reason = f"Gas concentration cleared to SAFE ({filtered_gas:.1f} ppm)"
                else:
                    new_risk = RiskLevel.WARNING
                    reason = f"Gas concentration de-escalated to WARNING ({filtered_gas:.1f} ppm)"
            else:
                new_risk = RiskLevel.DANGER
                reason = f"Gas concentration ({filtered_gas:.1f} ppm) maintaining DANGER state (hysteresis active)"

        elif self.current_risk == RiskLevel.CRITICAL:
            if filtered_gas < (c_thresh - hyst):
                if filtered_gas < (w_thresh - hyst):
                    new_risk = RiskLevel.SAFE
                    reason = f"Gas concentration cleared to SAFE ({filtered_gas:.1f} ppm)"
                elif filtered_gas < (d_thresh - hyst):
                    new_risk = RiskLevel.WARNING
                    reason = f"Gas concentration de-escalated to WARNING ({filtered_gas:.1f} ppm)"
                else:
                    new_risk = RiskLevel.DANGER
                    reason = f"Gas concentration de-escalated to DANGER ({filtered_gas:.1f} ppm)"
            else:
                new_risk = RiskLevel.CRITICAL
                reason = f"Gas concentration ({filtered_gas:.1f} ppm) maintaining CRITICAL state"

        # 2. Rate-of-Rise Escalation Rule
        # A rapid rate-of-rise overrides moderate concentration to immediately escalate alert
        if rapid_rise:
            if new_risk in (RiskLevel.SAFE, RiskLevel.WARNING):
                new_risk = RiskLevel.DANGER
                reason += f" | RAPID GAS RISE TRIGGER: +{rate_per_second:.1f} ppm/s exceeds threshold (+{self.thresholds.rate_of_rise_threshold:.1f} ppm/s)"
            elif new_risk == RiskLevel.DANGER:
                new_risk = RiskLevel.CRITICAL
                reason += f" | CRITICAL SURGE: +{rate_per_second:.1f} ppm/s rapid increase escalated to CRITICAL"

        self.current_risk = new_risk
        self.last_reason = reason
        return new_risk, rapid_rise, reason

    def reset(self) -> None:
        """Reset risk engine state."""
        self.current_risk = RiskLevel.SAFE
        self.last_rapid_rise = False
        self.last_reason = "Nominal safe environment"

