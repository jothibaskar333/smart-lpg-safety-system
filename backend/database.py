"""
SQLite Database Layer for Smart LPG Leak Detection & Automatic Shut-Off System.
Provides persistent storage for sensor telemetry, safety events, and system analytics.
"""

from __future__ import annotations
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional

from backend.config import settings


class DatabaseManager:
    """Thread-safe SQLite database manager."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = Path(db_path or settings.database_path)
        self._lock = threading.Lock()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Create tables and indexes if they do not exist."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Table: sensor_readings
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sensor_readings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    raw_gas REAL NOT NULL,
                    filtered_gas REAL NOT NULL,
                    rate_of_change REAL NOT NULL,
                    rate_per_second REAL NOT NULL,
                    temperature REAL NOT NULL,
                    humidity REAL NOT NULL,
                    sensor_status TEXT NOT NULL,
                    is_anomaly INTEGER NOT NULL DEFAULT 0,
                    anomaly_score REAL NOT NULL DEFAULT 0.0
                )
            """)

            # Table: events
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    gas_value REAL NOT NULL,
                    risk_level TEXT NOT NULL,
                    valve_state TEXT NOT NULL,
                    description TEXT NOT NULL
                )
            """)

            # Indexes for high-performance dashboard polling & analytics
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_readings_ts ON sensor_readings(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_ts ON events(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_risk ON events(risk_level)")
            
            conn.commit()

    def log_reading(
        self,
        raw_gas: float,
        filtered_gas: float,
        rate_of_change: float,
        rate_per_second: float,
        temperature: float,
        humidity: float,
        sensor_status: str,
        is_anomaly: bool = False,
        anomaly_score: float = 0.0,
        timestamp: Optional[str] = None
    ) -> int:
        """Log a new sensor measurement."""
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO sensor_readings (
                    timestamp, raw_gas, filtered_gas, rate_of_change, rate_per_second,
                    temperature, humidity, sensor_status, is_anomaly, anomaly_score
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ts, raw_gas, filtered_gas, rate_of_change, rate_per_second,
                temperature, humidity, sensor_status, 1 if is_anomaly else 0, anomaly_score
            ))
            conn.commit()
            return cursor.lastrowid or 0

    def log_event(
        self,
        event_type: str,
        gas_value: float,
        risk_level: str,
        valve_state: str,
        description: str,
        timestamp: Optional[str] = None
    ) -> int:
        """Log a system safety or state transition event."""
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO events (
                    timestamp, event_type, gas_value, risk_level, valve_state, description
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (ts, event_type, gas_value, risk_level, valve_state, description))
            conn.commit()
            return cursor.lastrowid or 0

    def get_recent_readings(self, limit: int = 60) -> List[Dict[str, Any]]:
        """Retrieve the most recent sensor readings sorted chronologically."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM (
                    SELECT * FROM sensor_readings ORDER BY id DESC LIMIT ?
                ) ORDER BY id ASC
            """, (limit,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_events(
        self,
        limit: int = 100,
        event_type: Optional[str] = None,
        risk_level: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve recent events with optional filtering."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM events WHERE 1=1"
            params: List[Any] = []

            if event_type:
                query += " AND event_type = ?"
                params.append(event_type)
            if risk_level:
                query += " AND risk_level = ?"
                params.append(risk_level)

            query += " ORDER BY id DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_analytics_summary(self) -> Dict[str, Any]:
        """Aggregate safety metrics and hourly trends."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()

            # Readings aggregates
            cursor.execute("""
                SELECT 
                    COALESCE(MAX(raw_gas), 0.0) as max_gas,
                    COALESCE(AVG(raw_gas), 0.0) as avg_gas,
                    COUNT(*) as total_readings,
                    COALESCE(MIN(timestamp), '') as min_ts,
                    COALESCE(MAX(timestamp), '') as max_ts
                FROM sensor_readings
            """)
            reading_stats = dict(cursor.fetchone())

            # Event counts
            cursor.execute("SELECT COUNT(*) FROM events WHERE event_type = 'GAS_WARNING' OR risk_level = 'WARNING'")
            warning_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM events WHERE event_type = 'GAS_DANGER' OR risk_level = 'DANGER'")
            danger_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM events WHERE event_type = 'GAS_CRITICAL' OR risk_level = 'CRITICAL'")
            critical_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM events WHERE event_type IN ('AUTOMATIC_SHUTOFF', 'MANUAL_SHUTOFF')")
            shutoff_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM events WHERE event_type = 'SENSOR_FAULT'")
            fault_count = cursor.fetchone()[0]

            # Calculate total monitoring time in seconds
            total_monitoring_seconds = 0.0
            if reading_stats["min_ts"] and reading_stats["max_ts"]:
                try:
                    t_min = datetime.fromisoformat(reading_stats["min_ts"])
                    t_max = datetime.fromisoformat(reading_stats["max_ts"])
                    total_monitoring_seconds = max(0.0, (t_max - t_min).total_seconds())
                except Exception:
                    total_monitoring_seconds = reading_stats["total_readings"] * settings.simulation_interval_sec

            # Hourly Trends (last 24 hours of data points)
            cursor.execute("""
                SELECT 
                    substr(timestamp, 1, 13) || ':00' as hour_bucket,
                    AVG(raw_gas) as avg_gas,
                    MAX(raw_gas) as max_gas,
                    COUNT(*) as readings_count
                FROM sensor_readings
                GROUP BY hour_bucket
                ORDER BY hour_bucket DESC
                LIMIT 24
            """)
            hourly_rows = cursor.fetchall()
            hourly_trends = [
                {
                    "hour": row["hour_bucket"],
                    "avg_gas": round(row["avg_gas"], 2),
                    "max_gas": round(row["max_gas"], 2),
                    "readings_count": row["readings_count"]
                }
                for row in reversed(hourly_rows)
            ]

            # Recent events sample
            cursor.execute("SELECT * FROM events ORDER BY id DESC LIMIT 15")
            recent_events = [dict(r) for r in cursor.fetchall()]

            return {
                "max_gas_ppm": round(reading_stats["max_gas"], 2),
                "avg_gas_ppm": round(reading_stats["avg_gas"], 2),
                "warning_count": warning_count,
                "danger_count": danger_count,
                "critical_count": critical_count,
                "shutoff_count": shutoff_count,
                "sensor_fault_count": fault_count,
                "total_readings": reading_stats["total_readings"],
                "total_monitoring_seconds": round(total_monitoring_seconds, 1),
                "hourly_trends": hourly_trends,
                "recent_events": recent_events,
            }

    def clear_all(self) -> None:
        """Purge all stored data (used for testing or system reset)."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM sensor_readings")
            cursor.execute("DELETE FROM events")
            conn.commit()


# Singleton database instance
db = DatabaseManager()

