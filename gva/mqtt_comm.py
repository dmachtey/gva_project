"""
mqtt_comm.py
============
Capa de Infraestructura — GVA Control de Emergencia
Publicación de eventos al broker MQTT.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MQTTResult:
    status:  str
    topic:   str
    packet:  str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class MQTTComm:
    """Simula la publicación MQTT. En producción usa paho-mqtt o aiomqtt."""

    CONNECT_DELAY_MS: int = 400

    def __init__(
        self,
        broker_url: str = "mqtt://broker.gva-local:1883",
        unit_id:    str = "GVA-07",
        sector:     str = "ALMACÉN-3",
    ) -> None:
        self._broker = broker_url
        self._unit   = unit_id
        self._sector = sector
        logger.info("[MQTT] MQTTComm inicializado. Broker: %s", broker_url)

    async def publish(self, topic: str, payload: dict) -> dict:
        logger.info("[MQTT] Conectando a broker %s...", self._broker)
        await asyncio.sleep(self.CONNECT_DELAY_MS / 1000)

        full_payload = {
            **payload,
            "ts":     datetime.now().isoformat(),
            "unit":   self._unit,
            "sector": self._sector,
        }
        packet = json.dumps(full_payload, ensure_ascii=False)

        logger.info("[MQTT] PUBLISH → %s", topic)
        logger.warning("[MQTT] Payload: %s", packet)
        logger.info("[MQTT] ✓ Mensaje publicado. ACK recibido del broker.")

        return MQTTResult(status="OK", topic=topic, packet=packet).__dict__
