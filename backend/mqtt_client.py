"""
MQTT Telemetry and Alert Publisher (Paho MQTT).
Connects to local or remote Mosquitto broker if enabled/available,
with automatic graceful degradation when no broker is present.
"""

from __future__ import annotations
import json
import logging
from typing import Dict, Any, Optional
from backend.config import settings

logger = logging.getLogger("smart_lpg.mqtt")


class MQTTClientHandler:
    """Manages publishing of telemetry and alert messages over MQTT."""

    def __init__(self):
        self.enabled = settings.mqtt.enabled
        self.host = settings.mqtt.broker_host
        self.port = settings.mqtt.broker_port
        self.telemetry_topic = settings.mqtt.telemetry_topic
        self.alerts_topic = settings.mqtt.alerts_topic
        self._client = None
        self._connected = False

        if self.enabled:
            self.connect()

    def connect(self) -> bool:
        """Attempt to connect to MQTT broker."""
        try:
            import paho.mqtt.client as mqtt  # type: ignore
            # Support both paho-mqtt v1 and v2 API
            try:
                self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, "SmartLPGSystem")
            except (AttributeError, TypeError):
                self._client = mqtt.Client("SmartLPGSystem")

            def on_connect(client, userdata, flags, rc, properties=None):
                if rc == 0:
                    self._connected = True
                    logger.info("Connected to MQTT broker %s:%s", self.host, self.port)
                else:
                    self._connected = False
                    logger.warning("MQTT connection failed with code %s", rc)

            def on_disconnect(client, userdata, rc, properties=None):
                self._connected = False
                logger.info("Disconnected from MQTT broker")

            self._client.on_connect = on_connect
            self._client.on_disconnect = on_disconnect

            self._client.connect_async(self.host, self.port, keepalive=60)
            self._client.loop_start()
            return True
        except Exception as e:
            logger.debug("MQTT broker not accessible (%s). Operating in standalone mode.", e)
            self._connected = False
            return False

    def publish_telemetry(self, data: Dict[str, Any]) -> None:
        """Publish real-time telemetry dictionary to MQTT topic."""
        if not self._connected or not self._client:
            return
        try:
            payload = json.dumps(data)
            self._client.publish(self.telemetry_topic, payload, qos=0)
        except Exception as e:
            logger.debug("Failed to publish telemetry to MQTT: %s", e)

    def publish_alert(self, alert_data: Dict[str, Any]) -> None:
        """Publish critical alert event to MQTT topic."""
        if not self._connected or not self._client:
            return
        try:
            payload = json.dumps(alert_data)
            self._client.publish(self.alerts_topic, payload, qos=1)
        except Exception as e:
            logger.debug("Failed to publish alert to MQTT: %s", e)

    def disconnect(self) -> None:
        """Cleanly disconnect client."""
        if self._client:
            try:
                self._client.loop_stop()
                self._client.disconnect()
            except Exception:
                pass
            self._connected = False


# Singleton instance
mqtt_handler = MQTTClientHandler()
