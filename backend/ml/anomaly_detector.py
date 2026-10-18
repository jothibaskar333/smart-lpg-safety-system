"""
Machine Learning Anomaly Detection Module using Isolation Forest.

IMPORTANT ARCHITECTURAL PRINCIPLE:
This ML module provides advisory anomaly scoring for early trend warning
and operational diagnostics. It DOES NOT replace or override the deterministic
safety rules. Deterministic thresholds and rate-of-rise interlocks ALWAYS maintain
absolute priority over physical shut-off valve actuators.
"""

from __future__ import annotations
import os
import pickle
import numpy as np
from pathlib import Path
from typing import Tuple, Optional
from backend.config import settings


class AnomalyDetector:
    """
    Unsupervised Anomaly Detector using scikit-learn Isolation Forest.
    Analyzes 4 multivariate dimensions:
    [gas_concentration, rate_per_second, temperature, humidity]
    """

    def __init__(
        self,
        contamination: float = settings.ml.contamination_rate,
        model_path: Optional[Path] = None
    ):
        self.contamination = contamination
        self.model_path = model_path or settings.ml.model_save_path
        self._model = None
        self._is_trained = False
        self._init_model()

    def _init_model(self) -> None:
        """Attempt to load saved model or train a synthetic baseline."""
        try:
            from sklearn.ensemble import IsolationForest  # type: ignore
            self._IsolationForest = IsolationForest
            self._sklearn_available = True
        except ImportError:
            self._IsolationForest = None
            self._sklearn_available = False

        if self.model_path.exists():
            try:
                with open(self.model_path, "rb") as f:
                    self._model = pickle.load(f)
                    self._is_trained = True
                    return
            except Exception:
                pass

        if self._sklearn_available:
            self.train_baseline()
        else:
            self._is_trained = True

    def train_baseline(self, num_samples: int = 500) -> None:
        """
        Train the Isolation Forest on synthetic nominal baseline environmental data.
        Nominal operating envelope:
            gas: 30 - 90 ppm
            rate: -3.0 to +3.0 ppm/s
            temp: 20 - 28 C
            humidity: 40 - 60 %
        """
        if not self._sklearn_available:
            self._is_trained = True
            return

        np.random.seed(42)
        gas = np.random.normal(60.0, 12.0, num_samples)
        rate = np.random.normal(0.0, 1.5, num_samples)
        temp = np.random.normal(24.5, 1.8, num_samples)
        hum = np.random.normal(52.0, 3.5, num_samples)

        X = np.column_stack([gas, rate, temp, hum])

        self._model = self._IsolationForest(
            n_estimators=100,
            contamination=self.contamination,
            random_state=42
        )
        self._model.fit(X)
        self._is_trained = True

        # Save to disk
        try:
            self.model_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.model_path, "wb") as f:
                pickle.dump(self._model, f)
        except Exception:
            pass

    def predict(
        self,
        gas_ppm: float,
        rate_per_sec: float,
        temp_c: float,
        humidity_pct: float
    ) -> Tuple[bool, float, str]:
        """
        Evaluate if a measurement vector is an anomaly.
        Returns:
            (is_anomaly: bool, anomaly_score: float, label: 'NORMAL' | 'ANOMALY')
        """
        if not self._is_trained or self._model is None:
            # Fallback heuristic if scikit-learn is unavailable
            is_anom = (
                gas_ppm > 250.0 or
                abs(rate_per_sec) > 20.0 or
                temp_c > 45.0 or
                temp_c < 0.0
            )
            score = -0.6 if is_anom else 0.4
            return is_anom, score, "ANOMALY" if is_anom else "NORMAL"

        X = np.array([[gas_ppm, rate_per_sec, temp_c, humidity_pct]])
        try:
            pred = self._model.predict(X)[0]  # 1 for inlier (normal), -1 for outlier (anomaly)
            score = float(self._model.decision_function(X)[0])  # lower = more anomalous
            is_anomaly = bool(pred == -1)
            label = "ANOMALY" if is_anomaly else "NORMAL"
            return is_anomaly, round(score, 3), label
        except Exception:
            return False, 0.0, "NORMAL"


# Singleton instance
anomaly_detector = AnomalyDetector()
