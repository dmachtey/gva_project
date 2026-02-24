"""
motor_hal.py
============
Hardware Abstraction Layer — GVA Control de Emergencia
Abstrae el control físico del motor y el relé de potencia.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class RelayState(str, Enum):
    CLOSED = "CLOSED"   # Energizado — motor activo
    OPEN   = "OPEN"     # Desenergizado — motor cortado


@dataclass(frozen=True)
class HALResult:
    status:      str
    relay:       RelayState
    unit_id:     str
    timestamp:   str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return {
            "status":    self.status,
            "relay":     self.relay.value,
            "unit_id":   self.unit_id,
            "timestamp": self.timestamp,
        }


class MotorHAL:
    """
    Abstracción del hardware del motor GVA.

    En producción, este módulo se comunica con el PLC/controlador
    físico vía GPIO, CANbus o Modbus. En esta implementación
    simula el comportamiento con delays y logs.

    El delay de 350ms emula el tiempo real de apertura del relé
    electromecánico de potencia del motor.
    """

    RELAY_OPEN_DELAY_MS: int = 350

    def __init__(self, unit_id: str = "GVA-07") -> None:
        self._unit_id    = unit_id
        self._relay_state = RelayState.CLOSED
        logger.info(
            "[HAL] MotorHAL inicializado. Unidad: %s. Relé: %s",
            unit_id, self._relay_state.value
        )

    @property
    def relay_state(self) -> RelayState:
        return self._relay_state

    async def cortar_energia(self) -> dict:
        """Abre el relé de potencia y corta la energía al motor."""
        logger.info("[HAL] Enviando señal CORTE al controlador de potencia...")
        await asyncio.sleep(self.RELAY_OPEN_DELAY_MS / 1000)
        self._relay_state = RelayState.OPEN
        result = HALResult(
            status="OK",
            relay=RelayState.OPEN,
            unit_id=self._unit_id,
        )
        logger.info("[HAL] Relé de potencia ABIERTO. Energía cortada.")
        return result.to_dict()

    async def restaurar_energia(self) -> dict:
        """Cierra el relé de potencia y restaura la energía al motor."""
        logger.info("[HAL] Restaurando energía al motor...")
        await asyncio.sleep(self.RELAY_OPEN_DELAY_MS / 1000)
        self._relay_state = RelayState.CLOSED
        result = HALResult(
            status="OK",
            relay=RelayState.CLOSED,
            unit_id=self._unit_id,
        )
        logger.info("[HAL] Relé de potencia CERRADO. Energía restaurada.")
        return result.to_dict()
