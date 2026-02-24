"""
safety_orchestrator.py
======================
Caso de Uso Central — GVA Control de Emergencia
Orquesta la secuencia de Paro de Emergencia coordinando
MotorHAL, StateManager y MQTTComm en el orden correcto.

Secuencia:
    1. MotorHAL.cortar_energia()      → Corte físico de potencia
    2. StateManager.cambiar_estado()  → Actualización del dominio
    3. MQTTComm.publish()             → Notificación al broker

El orquestador es idempotente: si ya está ejecutando una
secuencia, ignora llamadas adicionales (guard clause).
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from state_manager import StateManager, StateChangeResult, SystemState

logger = logging.getLogger(__name__)


# ── DTOs de resultado ────────────────────────────────────────────────────────

@dataclass(frozen=True)
class EmergencyStopResult:
    status:       str
    hal_result:   dict
    state_result: StateChangeResult
    mqtt_result:  dict
    duration_ms:  float
    timestamp:    str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass(frozen=True)
class ResetResult:
    status:    str
    duration_ms: float
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


# ── Excepciones ──────────────────────────────────────────────────────────────

class OrchestratorBusyError(Exception):
    """Se lanza cuando se llama a trigger() mientras ya está corriendo."""
    pass


class EmergencyStopFailedError(Exception):
    """Se lanza si algún paso de la secuencia falla."""
    pass


# ── SafetyOrchestrator ───────────────────────────────────────────────────────

class SafetyOrchestrator:
    """
    Caso de uso central del sistema GVA de seguridad.

    Coordina las tres capas del sistema en orden secuencial garantizado.
    Implementa el patrón Orchestrator con guard clause para evitar
    ejecuciones concurrentes del mismo evento de emergencia.

    Dependencias inyectadas (Clean Architecture):
        - motor_hal:     MotorHAL   — capa de hardware
        - state_manager: StateManager — capa de dominio
        - mqtt_comm:     MQTTComm   — capa de infraestructura

    Uso:
        orch = SafetyOrchestrator(hal, state_manager, mqtt)
        result = await orch.trigger()
        print(result.status)  # "OK"
    """

    STEP_DELAY_MS:    int = 200   # Delay entre pasos para observabilidad
    POST_STOP_DELAY_MS: int = 300 # Delay final antes de reportar completado

    MQTT_TOPIC_EMERGENCY: str = "gva/07/safety/emergency"
    MQTT_TOPIC_RESTORE:   str = "gva/07/safety/restore"

    def __init__(
        self,
        motor_hal,
        state_manager: StateManager,
        mqtt_comm,
    ) -> None:
        self._hal:   object        = motor_hal
        self._state: StateManager  = state_manager
        self._mqtt:  object        = mqtt_comm
        self._running: bool        = False
        self._last_result: Optional[EmergencyStopResult] = None

    # ── Propiedades públicas ─────────────────────────────────────────────────

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def last_result(self) -> Optional[EmergencyStopResult]:
        return self._last_result

    # ── Caso de uso principal ────────────────────────────────────────────────

    async def trigger(self) -> EmergencyStopResult:
        """
        Ejecuta la secuencia completa de Paro de Emergencia.

        Pasos:
            1. Corte de energía vía MotorHAL          (350ms)
            2. Cambio de estado vía StateManager       (300ms)
            3. Publicación MQTT vía MQTTComm           (400ms)

        Returns:
            EmergencyStopResult con resultados de cada paso.

        Raises:
            OrchestratorBusyError:    Si ya hay una secuencia en curso.
            EmergencyStopFailedError: Si algún paso falla.
        """
        if self._running:
            raise OrchestratorBusyError(
                "SafetyOrchestrator ya está ejecutando una secuencia. "
                "Ignorando llamada duplicada."
            )

        self._running = True
        t_start = asyncio.get_event_loop().time()

        logger.error(
            "[ORCH] ══ SECUENCIA DE PARO DE EMERGENCIA INICIADA ══"
        )

        try:
            # ── Paso 1/3: HAL ────────────────────────────────────────────────
            logger.info("[ORCH] Paso 1/3 → Corte de energía vía MotorHAL")
            hal_result = await self._hal.cortar_energia()
            logger.info("[ORCH] HAL retornó: %s", hal_result)
            await asyncio.sleep(self.STEP_DELAY_MS / 1000)

            # ── Paso 2/3: StateManager ───────────────────────────────────────
            logger.info("[ORCH] Paso 2/3 → Actualización de estado vía StateManager")
            state_result = await self._state.cambiar_estado(SystemState.EMERGENCY_STOP)
            logger.info("[ORCH] StateManager retornó: %s", state_result)
            await asyncio.sleep(self.STEP_DELAY_MS / 1000)

            # ── Paso 3/3: MQTT ───────────────────────────────────────────────
            logger.info("[ORCH] Paso 3/3 → Notificación vía MQTTComm")
            mqtt_payload = {
                "event":     "EMERGENCY_STOP",
                "trigger":   "MANUAL_BUTTON",
                "hal_status": hal_result.get("relay"),
                "state":     state_result.state.value,
            }
            mqtt_result = await self._mqtt.publish(
                self.MQTT_TOPIC_EMERGENCY,
                mqtt_payload,
            )
            logger.info("[ORCH] MQTTComm retornó: %s", mqtt_result)

            await asyncio.sleep(self.POST_STOP_DELAY_MS / 1000)

            duration_ms = (asyncio.get_event_loop().time() - t_start) * 1000
            logger.error(
                "[ORCH] ══ PARO DE EMERGENCIA COMPLETADO — %.0fms ══",
                duration_ms,
            )
            logger.info("[ORCH] Sistema en modo seguro. Esperando acción de operador.")

            self._last_result = EmergencyStopResult(
                status="OK",
                hal_result=hal_result,
                state_result=state_result,
                mqtt_result=mqtt_result,
                duration_ms=round(duration_ms, 2),
            )
            return self._last_result

        except Exception as exc:
            duration_ms = (asyncio.get_event_loop().time() - t_start) * 1000
            logger.critical(
                "[ORCH] ✗ FALLO EN SECUENCIA DE EMERGENCIA (%.0fms): %s",
                duration_ms, exc,
            )
            raise EmergencyStopFailedError(
                f"La secuencia de paro de emergencia falló: {exc}"
            ) from exc

        finally:
            # NUNCA liberar el lock automáticamente tras un EMERGENCY_STOP real.
            # Solo SystemReset debe hacer self._running = False.
            # En este diseño dejamos el lock activo para forzar el reset manual.
            pass

    async def reset(self) -> ResetResult:
        """
        Restablece el sistema al estado NORMAL tras un paro de emergencia.

        Solo puede ejecutarse si el sistema está en estado EMERGENCY_STOP.

        Returns:
            ResetResult con duración y timestamp.
        """
        logger.warning("[ORCH] ── Iniciando secuencia de restablecimiento... ──")
        t_start = asyncio.get_event_loop().time()

        await asyncio.sleep(0.3)

        # Restaurar estado de dominio
        await self._state.cambiar_estado(SystemState.RESTORING)
        await asyncio.sleep(0.1)
        await self._state.cambiar_estado(SystemState.NORMAL)

        # Notificar al broker
        await self._mqtt.publish(
            self.MQTT_TOPIC_RESTORE,
            {
                "event":   "SYSTEM_RESTORED",
                "trigger": "OPERATOR_MANUAL",
            },
        )

        self._running = False
        duration_ms = (asyncio.get_event_loop().time() - t_start) * 1000

        logger.info(
            "[ORCH] ── Sistema restablecido correctamente (%.0fms) ──",
            duration_ms,
        )

        return ResetResult(
            status="OK",
            duration_ms=round(duration_ms, 2),
        )
