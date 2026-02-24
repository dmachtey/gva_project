"""
gva/
====
Paquete GVA — Sistema de Control de Emergencia para Vehículo Móvil de Carga.

Arquitectura (Clean Architecture):
    ┌─────────────────────────────────────────────────┐
    │  SafetyOrchestrator  ← Caso de Uso / Entrada   │
    │  ┌───────────────────────────────────────────┐  │
    │  │  StateManager       MQTTComm              │  │  Dominio / Infraestructura
    │  │  ┌─────────────────────────────────────┐  │  │
    │  │  │        MotorHAL                     │  │  │  Hardware Abstraction Layer
    │  │  └─────────────────────────────────────┘  │  │
    │  └───────────────────────────────────────────┘  │
    └─────────────────────────────────────────────────┘

Módulos:
    state_manager        → Máquina de estados del dominio
    safety_orchestrator  → Coordinador de la secuencia de emergencia
    motor_hal            → Abstracción del hardware del motor
    mqtt_comm            → Comunicación con el broker MQTT

Uso rápido:
    from gva import SafetyOrchestrator, StateManager, SystemState
    from gva import MotorHAL, MQTTComm

    hal   = MotorHAL()
    state = StateManager()
    mqtt  = MQTTComm(broker_url="mqtt://broker.gva-local:1883")
    orch  = SafetyOrchestrator(hal, state, mqtt)

    import asyncio
    result = asyncio.run(orch.trigger())
    print(result.status)  # "OK"
"""

from __future__ import annotations

# ── Estado y dominio ─────────────────────────────────────────────────────────
from state_manager import (
    StateManager,
    SystemState,
    StateChangeResult,
    InvalidStateTransitionError,
    VALID_TRANSITIONS,
)

# ── Orquestador ──────────────────────────────────────────────────────────────
from safety_orchestrator import (
    SafetyOrchestrator,
    EmergencyStopResult,
    ResetResult,
    OrchestratorBusyError,
    EmergencyStopFailedError,
)

# ── Hardware y comunicaciones ─────────────────────────────────────────────────
from motor_hal import MotorHAL, HALResult, RelayState
from mqtt_comm import MQTTComm, MQTTResult


# ── API pública del paquete ──────────────────────────────────────────────────
__all__ = [
    # Dominio
    "StateManager",
    "SystemState",
    "StateChangeResult",
    "InvalidStateTransitionError",
    "VALID_TRANSITIONS",
    # Orquestador
    "SafetyOrchestrator",
    "EmergencyStopResult",
    "ResetResult",
    "OrchestratorBusyError",
    "EmergencyStopFailedError",
    # Hardware
    "MotorHAL",
    "HALResult",
    "RelayState",
    # Comunicaciones
    "MQTTComm",
    "MQTTResult",
]

__version__ = "1.0.0"
__author__  = "Equipo Ingeniería GVA"
__unit__    = "GVA-07"
__sector__  = "ALMACÉN-3"


# ── Factory helper ───────────────────────────────────────────────────────────

def create_gva_system(
    broker_url: str = "mqtt://broker.gva-local:1883",
    unit_id:    str = "GVA-07",
    sector:     str = "ALMACÉN-3",
) -> SafetyOrchestrator:
    """
    Factory que construye el sistema GVA completo con dependencias conectadas.

    Args:
        broker_url: URL del broker MQTT.
        unit_id:    Identificador de la unidad GVA.
        sector:     Sector de operación.

    Returns:
        SafetyOrchestrator listo para usar.

    Ejemplo:
        orch = create_gva_system()
        result = await orch.trigger()
    """
    hal   = MotorHAL(unit_id=unit_id)
    state = StateManager()
    mqtt  = MQTTComm(
        broker_url=broker_url,
        unit_id=unit_id,
        sector=sector,
    )
    return SafetyOrchestrator(hal, state, mqtt)
