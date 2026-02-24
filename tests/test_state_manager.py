"""
test_state_manager.py
=====================
Tests unitarios para la capa de dominio StateManager.
Cubre: estados, transiciones válidas e inválidas,
historial, callbacks, propiedades y reset forzado.

Ejecutar:
    pytest test_state_manager.py -v
"""

import pytest
import pytest_asyncio
from unittest.mock import MagicMock

from state_manager import (
    StateManager,
    SystemState,
    StateChangeResult,
    InvalidStateTransitionError,
    VALID_TRANSITIONS,
)


# ══════════════════════════════════════════════════════════════════
#  FIXTURES
# ══════════════════════════════════════════════════════════════════

@pytest.fixture
def manager():
    """StateManager limpio en estado NORMAL."""
    return StateManager()


@pytest.fixture
def manager_en_emergency():
    """StateManager ya en estado EMERGENCY_STOP (usando reset interno)."""
    m = StateManager()
    m._state = SystemState.EMERGENCY_STOP
    m._history.append((SystemState.EMERGENCY_STOP, "2026-01-01T00:00:00"))
    return m


# ══════════════════════════════════════════════════════════════════
#  SUITE 1 — Estado inicial y propiedades
# ══════════════════════════════════════════════════════════════════

class TestEstadoInicial:

    def test_estado_inicial_es_normal(self, manager):
        """TC-SM-01: El estado por defecto debe ser NORMAL."""
        assert manager.current_state == SystemState.NORMAL

    def test_estado_inicial_personalizado(self):
        """TC-SM-02: Se puede inicializar con un estado personalizado."""
        m = StateManager(initial_state=SystemState.EMERGENCY_STOP)
        assert m.current_state == SystemState.EMERGENCY_STOP

    def test_historial_inicial_tiene_un_elemento(self, manager):
        """TC-SM-03: El historial comienza con exactamente un registro."""
        assert len(manager.history) == 1

    def test_historial_inicial_contiene_normal(self, manager):
        """TC-SM-04: El primer elemento del historial es el estado inicial."""
        estado, _ = manager.history[0]
        assert estado == SystemState.NORMAL

    def test_is_emergency_es_false_en_normal(self, manager):
        """TC-SM-05: is_emergency debe ser False cuando el estado es NORMAL."""
        assert manager.is_emergency is False

    def test_is_emergency_es_true_en_emergency(self, manager_en_emergency):
        """TC-SM-06: is_emergency debe ser True en EMERGENCY_STOP."""
        assert manager_en_emergency.is_emergency is True


# ══════════════════════════════════════════════════════════════════
#  SUITE 2 — Transiciones válidas
# ══════════════════════════════════════════════════════════════════

class TestTransicionesValidas:

    @pytest.mark.asyncio
    async def test_normal_a_emergency_stop(self, manager):
        """TC-SM-07: NORMAL → EMERGENCY_STOP es una transición válida."""
        result = await manager.cambiar_estado(SystemState.EMERGENCY_STOP)
        assert manager.current_state == SystemState.EMERGENCY_STOP

    @pytest.mark.asyncio
    async def test_emergency_a_restoring(self, manager_en_emergency):
        """TC-SM-08: EMERGENCY_STOP → RESTORING es una transición válida."""
        result = await manager_en_emergency.cambiar_estado(SystemState.RESTORING)
        assert manager_en_emergency.current_state == SystemState.RESTORING

    @pytest.mark.asyncio
    async def test_restoring_a_normal(self):
        """TC-SM-09: RESTORING → NORMAL es una transición válida."""
        m = StateManager(initial_state=SystemState.RESTORING)
        await m.cambiar_estado(SystemState.NORMAL)
        assert m.current_state == SystemState.NORMAL

    @pytest.mark.asyncio
    async def test_secuencia_completa_ciclo(self, manager):
        """TC-SM-10: Ciclo completo NORMAL→EMERGENCY→RESTORING→NORMAL."""
        await manager.cambiar_estado(SystemState.EMERGENCY_STOP)
        await manager.cambiar_estado(SystemState.RESTORING)
        await manager.cambiar_estado(SystemState.NORMAL)
        assert manager.current_state == SystemState.NORMAL


# ══════════════════════════════════════════════════════════════════
#  SUITE 3 — Transiciones inválidas
# ══════════════════════════════════════════════════════════════════

class TestTransicionesInvalidas:

    @pytest.mark.asyncio
    async def test_normal_a_restoring_invalido(self, manager):
        """TC-SM-11: NORMAL → RESTORING debe lanzar InvalidStateTransitionError."""
        with pytest.raises(InvalidStateTransitionError) as exc:
            await manager.cambiar_estado(SystemState.RESTORING)
        assert "NORMAL" in str(exc.value)
        assert "RESTORING" in str(exc.value)

    @pytest.mark.asyncio
    async def test_normal_a_normal_invalido(self, manager):
        """TC-SM-12: NORMAL → NORMAL no está permitido."""
        with pytest.raises(InvalidStateTransitionError):
            await manager.cambiar_estado(SystemState.NORMAL)

    @pytest.mark.asyncio
    async def test_emergency_a_normal_invalido(self, manager_en_emergency):
        """TC-SM-13: EMERGENCY_STOP → NORMAL directo no está permitido."""
        with pytest.raises(InvalidStateTransitionError) as exc:
            await manager_en_emergency.cambiar_estado(SystemState.NORMAL)
        assert "EMERGENCY_STOP" in str(exc.value)

    @pytest.mark.asyncio
    async def test_estado_no_cambia_si_transicion_invalida(self, manager):
        """TC-SM-14: El estado NO debe cambiar si la transición falla."""
        with pytest.raises(InvalidStateTransitionError):
            await manager.cambiar_estado(SystemState.RESTORING)
        assert manager.current_state == SystemState.NORMAL


# ══════════════════════════════════════════════════════════════════
#  SUITE 4 — Resultado (DTO StateChangeResult)
# ══════════════════════════════════════════════════════════════════

class TestStateChangeResult:

    @pytest.mark.asyncio
    async def test_resultado_status_ok(self, manager):
        """TC-SM-15: El resultado debe tener status 'OK'."""
        result = await manager.cambiar_estado(SystemState.EMERGENCY_STOP)
        assert result.status == "OK"

    @pytest.mark.asyncio
    async def test_resultado_estado_correcto(self, manager):
        """TC-SM-16: El resultado debe reflejar el nuevo estado."""
        result = await manager.cambiar_estado(SystemState.EMERGENCY_STOP)
        assert result.state == SystemState.EMERGENCY_STOP

    @pytest.mark.asyncio
    async def test_resultado_previous_correcto(self, manager):
        """TC-SM-17: El resultado debe incluir el estado anterior."""
        result = await manager.cambiar_estado(SystemState.EMERGENCY_STOP)
        assert result.previous == SystemState.NORMAL

    @pytest.mark.asyncio
    async def test_resultado_tiene_timestamp(self, manager):
        """TC-SM-18: El resultado debe incluir un timestamp ISO."""
        result = await manager.cambiar_estado(SystemState.EMERGENCY_STOP)
        assert result.timestamp is not None
        assert "T" in result.timestamp  # formato ISO 8601

    @pytest.mark.asyncio
    async def test_resultado_es_inmutable(self, manager):
        """TC-SM-19: StateChangeResult es un dataclass frozen (inmutable)."""
        result = await manager.cambiar_estado(SystemState.EMERGENCY_STOP)
        with pytest.raises((AttributeError, TypeError)):
            result.status = "ERROR"  # type: ignore


# ══════════════════════════════════════════════════════════════════
#  SUITE 5 — Historial
# ══════════════════════════════════════════════════════════════════

class TestHistorial:

    @pytest.mark.asyncio
    async def test_historial_crece_con_transiciones(self, manager):
        """TC-SM-20: El historial debe crecer con cada transición."""
        assert len(manager.history) == 1
        await manager.cambiar_estado(SystemState.EMERGENCY_STOP)
        assert len(manager.history) == 2

    @pytest.mark.asyncio
    async def test_historial_refleja_secuencia_correcta(self, manager):
        """TC-SM-21: El historial debe registrar los estados en orden."""
        await manager.cambiar_estado(SystemState.EMERGENCY_STOP)
        await manager.cambiar_estado(SystemState.RESTORING)
        states = [h[0] for h in manager.history]
        assert states == [
            SystemState.NORMAL,
            SystemState.EMERGENCY_STOP,
            SystemState.RESTORING,
        ]

    @pytest.mark.asyncio
    async def test_historial_devuelve_copia(self, manager):
        """TC-SM-22: history debe devolver una copia (no la lista interna)."""
        h = manager.history
        h.append((SystemState.EMERGENCY_STOP, "fake"))
        assert len(manager.history) == 1  # la interna no debe verse afectada


# ══════════════════════════════════════════════════════════════════
#  SUITE 6 — Callback on_state_change
# ══════════════════════════════════════════════════════════════════

class TestCallback:

    @pytest.mark.asyncio
    async def test_callback_es_invocado(self):
        """TC-SM-23: El callback debe llamarse al cambiar de estado."""
        mock_cb = MagicMock()
        m = StateManager(on_state_change=mock_cb)
        await m.cambiar_estado(SystemState.EMERGENCY_STOP)
        mock_cb.assert_called_once()

    @pytest.mark.asyncio
    async def test_callback_recibe_estados_correctos(self):
        """TC-SM-24: El callback recibe (estado_anterior, estado_nuevo)."""
        mock_cb = MagicMock()
        m = StateManager(on_state_change=mock_cb)
        await m.cambiar_estado(SystemState.EMERGENCY_STOP)
        mock_cb.assert_called_once_with(
            SystemState.NORMAL,
            SystemState.EMERGENCY_STOP,
        )

    @pytest.mark.asyncio
    async def test_sin_callback_no_falla(self, manager):
        """TC-SM-25: Sin callback registrado no debe lanzar excepción."""
        result = await manager.cambiar_estado(SystemState.EMERGENCY_STOP)
        assert result.status == "OK"


# ══════════════════════════════════════════════════════════════════
#  SUITE 7 — Reset forzado
# ══════════════════════════════════════════════════════════════════

class TestReset:

    def test_reset_fuerza_estado_normal(self, manager_en_emergency):
        """TC-SM-26: reset() debe forzar el estado a NORMAL sin validación."""
        assert manager_en_emergency.current_state == SystemState.EMERGENCY_STOP
        manager_en_emergency.reset()
        assert manager_en_emergency.current_state == SystemState.NORMAL

    @pytest.mark.asyncio
    async def test_tras_reset_permite_transicion_a_emergency(self, manager_en_emergency):
        """TC-SM-27: Tras reset() se puede volver a disparar emergency."""
        manager_en_emergency.reset()
        result = await manager_en_emergency.cambiar_estado(SystemState.EMERGENCY_STOP)
        assert result.status == "OK"


# ══════════════════════════════════════════════════════════════════
#  SUITE 8 — Constantes y tabla de transiciones
# ══════════════════════════════════════════════════════════════════

class TestConstantes:

    def test_valid_transitions_cubre_todos_los_estados(self):
        """TC-SM-28: VALID_TRANSITIONS debe tener entrada para cada estado."""
        for state in SystemState:
            assert state in VALID_TRANSITIONS

    def test_delay_de_transicion_es_300ms(self):
        """TC-SM-29: TRANSITION_DELAY_MS debe ser 300."""
        assert StateManager.TRANSITION_DELAY_MS == 300

    def test_system_state_tiene_tres_valores(self):
        """TC-SM-30: El enum SystemState debe tener exactamente 3 valores."""
        assert len(SystemState) == 3
        assert SystemState.NORMAL         == "NORMAL"
        assert SystemState.EMERGENCY_STOP == "EMERGENCY_STOP"
        assert SystemState.RESTORING      == "RESTORING"
