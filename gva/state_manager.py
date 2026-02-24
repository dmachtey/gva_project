"""
state_manager.py
================
Capa de Dominio — GVA Control de Emergencia
Gestiona la máquina de estados del sistema GVA-07.

Estados válidos:
    NORMAL          → Operación estándar
    EMERGENCY_STOP  → Paro de emergencia activo
    RESTORING       → En proceso de restablecimiento
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable, Optional

logger = logging.getLogger(__name__)


# ── Enum de estados válidos ──────────────────────────────────────────────────

class SystemState(str, Enum):
    NORMAL         = "NORMAL"
    EMERGENCY_STOP = "EMERGENCY_STOP"
    RESTORING      = "RESTORING"


# ── DTOs de resultado ────────────────────────────────────────────────────────

@dataclass(frozen=True)
class StateChangeResult:
    status:    str
    state:     SystemState
    previous:  SystemState
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


# ── Excepciones de dominio ───────────────────────────────────────────────────

class InvalidStateTransitionError(Exception):
    """Se lanza cuando se intenta una transición de estado no permitida."""
    pass


# ── Transiciones permitidas ──────────────────────────────────────────────────

VALID_TRANSITIONS: dict[SystemState, list[SystemState]] = {
    SystemState.NORMAL:         [SystemState.EMERGENCY_STOP],
    SystemState.EMERGENCY_STOP: [SystemState.RESTORING],
    SystemState.RESTORING:      [SystemState.NORMAL],
}


# ── StateManager ─────────────────────────────────────────────────────────────

class StateManager:
    """
    Gestiona el estado del dominio GVA.

    Aplica el patrón State Machine con validación de transiciones.
    El delay de 300ms emula la latencia real del sistema embebido.

    Uso:
        manager = StateManager()
        result  = await manager.cambiar_estado(SystemState.EMERGENCY_STOP)
        print(result.state)   # SystemState.EMERGENCY_STOP
    """

    TRANSITION_DELAY_MS: int = 300

    def __init__(
        self,
        initial_state: SystemState = SystemState.NORMAL,
        on_state_change: Optional[Callable[[SystemState, SystemState], None]] = None,
    ) -> None:
        self._state:           SystemState = initial_state
        self._on_state_change: Optional[Callable] = on_state_change
        self._history:         list[tuple[SystemState, str]] = [
            (initial_state, datetime.now().isoformat())
        ]
        logger.info(
            "[STATE] StateManager inicializado. Estado: %s",
            self._state.value,
        )

    # ── Propiedades públicas ─────────────────────────────────────────────────

    @property
    def current_state(self) -> SystemState:
        return self._state

    @property
    def history(self) -> list[tuple[SystemState, str]]:
        """Devuelve el historial de estados con su timestamp."""
        return list(self._history)

    @property
    def is_emergency(self) -> bool:
        return self._state == SystemState.EMERGENCY_STOP

    # ── Lógica de transición ─────────────────────────────────────────────────

    async def cambiar_estado(self, new_state: SystemState) -> StateChangeResult:
        """
        Transiciona al nuevo estado con validación y delay simulado.

        Args:
            new_state: Estado destino de la transición.

        Returns:
            StateChangeResult con status OK y metadatos.

        Raises:
            InvalidStateTransitionError: Si la transición no está permitida.
        """
        self._validate_transition(new_state)

        previous = self._state
        logger.info(
            "[STATE] Transición: %s → %s",
            previous.value,
            new_state.value,
        )

        # Simula latencia del sistema embebido
        await asyncio.sleep(self.TRANSITION_DELAY_MS / 1000)

        self._state = new_state
        ts = datetime.now().isoformat()
        self._history.append((new_state, ts))

        if self._on_state_change:
            self._on_state_change(previous, new_state)

        if new_state == SystemState.EMERGENCY_STOP:
            logger.error(
                "[STATE] ⚠ Estado crítico activado: %s",
                new_state.value,
            )
        else:
            logger.info(
                "[STATE] Estado actualizado a: %s",
                new_state.value,
            )

        return StateChangeResult(
            status="OK",
            state=new_state,
            previous=previous,
            timestamp=ts,
        )

    def _validate_transition(self, new_state: SystemState) -> None:
        """Valida que la transición sea permitida según la máquina de estados."""
        allowed = VALID_TRANSITIONS.get(self._state, [])
        if new_state not in allowed:
            raise InvalidStateTransitionError(
                f"Transición inválida: {self._state.value} → {new_state.value}. "
                f"Permitidas desde {self._state.value}: "
                f"{[s.value for s in allowed]}"
            )

    def reset(self) -> None:
        """Fuerza el estado a NORMAL sin validación (solo para tests)."""
        self._state = SystemState.NORMAL
        logger.warning("[STATE] Reset forzado a NORMAL (uso interno)")
