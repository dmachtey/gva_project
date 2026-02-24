"""
test_safety_orchestrator.py
============================
Tests unitarios para el caso de uso central SafetyOrchestrator.
Todas las dependencias (HAL, StateManager, MQTT) se mockean con
AsyncMock para aislar el comportamiento del orquestador puro.

Ejecutar:
    pytest test_safety_orchestrator.py -v
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call
from dataclasses import dataclass

from state_manager import StateManager, SystemState, StateChangeResult
from safety_orchestrator import (
    SafetyOrchestrator,
    EmergencyStopResult,
    ResetResult,
    OrchestratorBusyError,
    EmergencyStopFailedError,
)


# ══════════════════════════════════════════════════════════════════
#  HELPERS — Mocks reutilizables
# ══════════════════════════════════════════════════════════════════

def make_hal_mock(relay="OPEN", status="OK"):
    """Crea un mock de MotorHAL que retorna un dict correcto."""
    hal = MagicMock()
    hal.cortar_energia = AsyncMock(return_value={
        "status": status,
        "relay":  relay,
        "unit_id": "GVA-07",
    })
    hal.restaurar_energia = AsyncMock(return_value={
        "status": "OK",
        "relay":  "CLOSED",
    })
    return hal


def make_mqtt_mock(status="OK"):
    """Crea un mock de MQTTComm que retorna un dict correcto."""
    mqtt = MagicMock()
    mqtt.publish = AsyncMock(return_value={
        "status": status,
        "topic":  "gva/07/safety/emergency",
        "packet": "{}",
    })
    return mqtt


def make_state_mock():
    """Crea un mock de StateManager."""
    state = MagicMock(spec=StateManager)
    state_result = StateChangeResult(
        status="OK",
        state=SystemState.EMERGENCY_STOP,
        previous=SystemState.NORMAL,
    )
    state.cambiar_estado = AsyncMock(return_value=state_result)
    state.current_state = SystemState.NORMAL
    return state


@pytest.fixture
def deps():
    """Devuelve las tres dependencias mockeadas listas para inyectar."""
    return make_hal_mock(), make_state_mock(), make_mqtt_mock()


@pytest.fixture
def orch(deps):
    """SafetyOrchestrator con dependencias mockeadas."""
    hal, state, mqtt = deps
    return SafetyOrchestrator(hal, state, mqtt)


# ══════════════════════════════════════════════════════════════════
#  SUITE 1 — Estado inicial del orquestador
# ══════════════════════════════════════════════════════════════════

class TestEstadoInicial:

    def test_is_running_es_false_al_inicio(self, orch):
        """TC-ORCH-01: is_running debe ser False antes de cualquier trigger."""
        assert orch.is_running is False

    def test_last_result_es_none_al_inicio(self, orch):
        """TC-ORCH-02: last_result debe ser None antes de cualquier trigger."""
        assert orch.last_result is None

    def test_constante_topic_emergency(self, orch):
        """TC-ORCH-03: El topic MQTT de emergencia debe ser el correcto."""
        assert orch.MQTT_TOPIC_EMERGENCY == "gva/07/safety/emergency"

    def test_constante_topic_restore(self, orch):
        """TC-ORCH-04: El topic MQTT de restore debe ser el correcto."""
        assert orch.MQTT_TOPIC_RESTORE == "gva/07/safety/restore"


# ══════════════════════════════════════════════════════════════════
#  SUITE 2 — Secuencia trigger() feliz
# ══════════════════════════════════════════════════════════════════

class TestTriggerSecuencia:

    @pytest.mark.asyncio
    async def test_trigger_llama_hal_primero(self, orch, deps):
        """TC-ORCH-05: cortar_energia() debe ser el primer paso llamado."""
        hal, state, mqtt = deps
        call_order = []
        hal.cortar_energia.side_effect    = lambda: call_order.append("HAL")   or {"status":"OK","relay":"OPEN"}
        state.cambiar_estado.side_effect  = lambda s: call_order.append("STATE") or StateChangeResult("OK", s, SystemState.NORMAL)
        mqtt.publish.side_effect          = lambda t, p: call_order.append("MQTT") or {"status":"OK","topic":t,"packet":"{}"}

        # Redefinir como AsyncMock con side_effect
        async def hal_fn():   call_order.append("HAL");   return {"status":"OK","relay":"OPEN"}
        async def state_fn(s): call_order.append("STATE"); return StateChangeResult("OK", s, SystemState.NORMAL)
        async def mqtt_fn(t,p): call_order.append("MQTT"); return {"status":"OK","topic":t,"packet":"{}"}

        hal.cortar_energia   = hal_fn
        state.cambiar_estado = state_fn
        mqtt.publish         = mqtt_fn

        await orch.trigger()
        assert call_order[0] == "HAL"

    @pytest.mark.asyncio
    async def test_trigger_orden_hal_state_mqtt(self, deps):
        """TC-ORCH-06: El orden de ejecución debe ser HAL → STATE → MQTT."""
        hal, state, mqtt = deps
        call_order = []

        async def hal_fn():    call_order.append("HAL");   return {"status":"OK","relay":"OPEN"}
        async def state_fn(s): call_order.append("STATE"); return StateChangeResult("OK", s, SystemState.NORMAL)
        async def mqtt_fn(t,p):call_order.append("MQTT");  return {"status":"OK","topic":t,"packet":"{}"}

        hal.cortar_energia   = hal_fn
        state.cambiar_estado = state_fn
        mqtt.publish         = mqtt_fn

        orch = SafetyOrchestrator(hal, state, mqtt)
        await orch.trigger()
        assert call_order == ["HAL", "STATE", "MQTT"]

    @pytest.mark.asyncio
    async def test_trigger_retorna_result_con_status_ok(self, orch):
        """TC-ORCH-07: trigger() debe retornar EmergencyStopResult con status OK."""
        result = await orch.trigger()
        assert result.status == "OK"

    @pytest.mark.asyncio
    async def test_trigger_retorna_emergency_stop_result(self, orch):
        """TC-ORCH-08: El tipo de retorno debe ser EmergencyStopResult."""
        result = await orch.trigger()
        assert isinstance(result, EmergencyStopResult)

    @pytest.mark.asyncio
    async def test_trigger_result_contiene_hal_result(self, orch):
        """TC-ORCH-09: El resultado debe incluir el retorno del HAL."""
        result = await orch.trigger()
        assert result.hal_result["relay"] == "OPEN"

    @pytest.mark.asyncio
    async def test_trigger_result_contiene_state_result(self, orch):
        """TC-ORCH-10: El resultado debe incluir el retorno del StateManager."""
        result = await orch.trigger()
        assert result.state_result.state == SystemState.EMERGENCY_STOP

    @pytest.mark.asyncio
    async def test_trigger_result_contiene_mqtt_result(self, orch):
        """TC-ORCH-11: El resultado debe incluir el retorno de MQTTComm."""
        result = await orch.trigger()
        assert result.mqtt_result["status"] == "OK"

    @pytest.mark.asyncio
    async def test_trigger_result_tiene_duration_ms(self, orch):
        """TC-ORCH-12: El resultado debe incluir la duración en ms."""
        result = await orch.trigger()
        assert result.duration_ms > 0

    @pytest.mark.asyncio
    async def test_trigger_almacena_last_result(self, orch):
        """TC-ORCH-13: Tras trigger(), last_result no debe ser None."""
        await orch.trigger()
        assert orch.last_result is not None
        assert orch.last_result.status == "OK"


# ══════════════════════════════════════════════════════════════════
#  SUITE 3 — Guard clause (idempotencia)
# ══════════════════════════════════════════════════════════════════

class TestGuardClause:

    @pytest.mark.asyncio
    async def test_trigger_lanza_busy_si_ya_running(self, orch):
        """TC-ORCH-14: Segundo trigger() lanza OrchestratorBusyError."""
        orch._running = True
        with pytest.raises(OrchestratorBusyError) as exc:
            await orch.trigger()
        assert "ejecutando" in str(exc.value).lower() or "busy" in str(exc.value).lower()

    @pytest.mark.asyncio
    async def test_hal_no_llamado_si_ya_running(self, orch, deps):
        """TC-ORCH-15: Si ya running, cortar_energia() no debe invocarse."""
        hal, _, _ = deps
        orch._running = True
        with pytest.raises(OrchestratorBusyError):
            await orch.trigger()
        hal.cortar_energia.assert_not_called()

    @pytest.mark.asyncio
    async def test_is_running_true_durante_ejecucion(self, deps):
        """TC-ORCH-16: is_running debe ser True mientras trigger() ejecuta."""
        hal, state, mqtt = deps
        running_during = []

        async def hal_fn():
            running_during.append(orch.is_running)
            return {"status": "OK", "relay": "OPEN"}

        hal.cortar_energia = hal_fn
        orch = SafetyOrchestrator(hal, state, mqtt)
        await orch.trigger()
        assert running_during[0] is True

    @pytest.mark.asyncio
    async def test_is_running_true_tras_trigger(self, orch):
        """TC-ORCH-17: is_running queda True tras trigger() (requiere reset manual)."""
        await orch.trigger()
        assert orch.is_running is True


# ══════════════════════════════════════════════════════════════════
#  SUITE 4 — Payload MQTT
# ══════════════════════════════════════════════════════════════════

class TestPayloadMQTT:

    @pytest.mark.asyncio
    async def test_mqtt_publish_llamado_con_topic_correcto(self, orch, deps):
        """TC-ORCH-18: publish() debe llamarse con el topic de emergencia."""
        _, _, mqtt = deps
        await orch.trigger()
        call_args = mqtt.publish.call_args
        assert call_args[0][0] == "gva/07/safety/emergency"

    @pytest.mark.asyncio
    async def test_mqtt_payload_contiene_event_emergency_stop(self, orch, deps):
        """TC-ORCH-19: El payload debe incluir event=EMERGENCY_STOP."""
        _, _, mqtt = deps
        await orch.trigger()
        payload = mqtt.publish.call_args[0][1]
        assert payload["event"] == "EMERGENCY_STOP"

    @pytest.mark.asyncio
    async def test_mqtt_payload_contiene_trigger_manual(self, orch, deps):
        """TC-ORCH-20: El payload debe indicar el trigger MANUAL_BUTTON."""
        _, _, mqtt = deps
        await orch.trigger()
        payload = mqtt.publish.call_args[0][1]
        assert payload["trigger"] == "MANUAL_BUTTON"

    @pytest.mark.asyncio
    async def test_mqtt_payload_contiene_hal_status(self, orch, deps):
        """TC-ORCH-21: El payload debe incluir el estado del relé del HAL."""
        _, _, mqtt = deps
        await orch.trigger()
        payload = mqtt.publish.call_args[0][1]
        assert payload["hal_status"] == "OPEN"

    @pytest.mark.asyncio
    async def test_mqtt_payload_contiene_state(self, orch, deps):
        """TC-ORCH-22: El payload debe incluir el nuevo estado del sistema."""
        _, _, mqtt = deps
        await orch.trigger()
        payload = mqtt.publish.call_args[0][1]
        assert payload["state"] == "EMERGENCY_STOP"


# ══════════════════════════════════════════════════════════════════
#  SUITE 5 — Manejo de errores
# ══════════════════════════════════════════════════════════════════

class TestManejoErrores:

    @pytest.mark.asyncio
    async def test_fallo_en_hal_lanza_emergency_stop_failed(self, deps):
        """TC-ORCH-23: Si HAL falla, debe lanzar EmergencyStopFailedError."""
        hal, state, mqtt = deps
        hal.cortar_energia = AsyncMock(side_effect=RuntimeError("GPIO error"))
        orch = SafetyOrchestrator(hal, state, mqtt)

        with pytest.raises(EmergencyStopFailedError) as exc:
            await orch.trigger()
        assert "GPIO error" in str(exc.value)

    @pytest.mark.asyncio
    async def test_fallo_en_state_lanza_emergency_stop_failed(self, deps):
        """TC-ORCH-24: Si StateManager falla, debe lanzar EmergencyStopFailedError."""
        hal, state, mqtt = deps
        state.cambiar_estado = AsyncMock(side_effect=ValueError("Estado inválido"))
        orch = SafetyOrchestrator(hal, state, mqtt)

        with pytest.raises(EmergencyStopFailedError) as exc:
            await orch.trigger()
        assert "Estado inválido" in str(exc.value)

    @pytest.mark.asyncio
    async def test_fallo_en_mqtt_lanza_emergency_stop_failed(self, deps):
        """TC-ORCH-25: Si MQTT falla, debe lanzar EmergencyStopFailedError."""
        hal, state, mqtt = deps
        mqtt.publish = AsyncMock(side_effect=ConnectionError("Broker no disponible"))
        orch = SafetyOrchestrator(hal, state, mqtt)

        with pytest.raises(EmergencyStopFailedError) as exc:
            await orch.trigger()
        assert "Broker no disponible" in str(exc.value)

    @pytest.mark.asyncio
    async def test_si_hal_falla_state_no_es_llamado(self, deps):
        """TC-ORCH-26: Si HAL falla, StateManager no debe ser invocado."""
        hal, state, mqtt = deps
        hal.cortar_energia = AsyncMock(side_effect=RuntimeError("HAL error"))
        orch = SafetyOrchestrator(hal, state, mqtt)

        with pytest.raises(EmergencyStopFailedError):
            await orch.trigger()
        state.cambiar_estado.assert_not_called()

    @pytest.mark.asyncio
    async def test_emergency_stop_failed_encadena_causa_original(self, deps):
        """TC-ORCH-27: EmergencyStopFailedError debe encadenar la excepción original."""
        hal, state, mqtt = deps
        original = RuntimeError("causa raíz")
        hal.cortar_energia = AsyncMock(side_effect=original)
        orch = SafetyOrchestrator(hal, state, mqtt)

        with pytest.raises(EmergencyStopFailedError) as exc_info:
            await orch.trigger()
        assert exc_info.value.__cause__ is original


# ══════════════════════════════════════════════════════════════════
#  SUITE 6 — Flujo reset()
# ══════════════════════════════════════════════════════════════════

class TestReset:

    @pytest.fixture
    def orch_post_stop(self, deps):
        """Orquestador después de un trigger() exitoso (simulado)."""
        hal, state, mqtt = deps
        orch = SafetyOrchestrator(hal, state, mqtt)
        orch._running = True
        # Simular que el state está en EMERGENCY_STOP→RESTORING→NORMAL
        resultados = [
            StateChangeResult("OK", SystemState.RESTORING, SystemState.EMERGENCY_STOP),
            StateChangeResult("OK", SystemState.NORMAL,    SystemState.RESTORING),
        ]
        state.cambiar_estado = AsyncMock(side_effect=resultados)
        return orch

    @pytest.mark.asyncio
    async def test_reset_retorna_reset_result(self, orch_post_stop):
        """TC-ORCH-28: reset() debe retornar un ResetResult."""
        result = await orch_post_stop.reset()
        assert isinstance(result, ResetResult)

    @pytest.mark.asyncio
    async def test_reset_status_ok(self, orch_post_stop):
        """TC-ORCH-29: El status del ResetResult debe ser OK."""
        result = await orch_post_stop.reset()
        assert result.status == "OK"

    @pytest.mark.asyncio
    async def test_reset_libera_is_running(self, orch_post_stop):
        """TC-ORCH-30: reset() debe poner is_running en False."""
        assert orch_post_stop.is_running is True
        await orch_post_stop.reset()
        assert orch_post_stop.is_running is False

    @pytest.mark.asyncio
    async def test_reset_publica_en_topic_restore(self, orch_post_stop, deps):
        """TC-ORCH-31: reset() debe publicar en el topic de restore."""
        _, _, mqtt = deps
        await orch_post_stop.reset()
        topic_usado = mqtt.publish.call_args[0][0]
        assert topic_usado == "gva/07/safety/restore"

    @pytest.mark.asyncio
    async def test_reset_payload_event_system_restored(self, orch_post_stop, deps):
        """TC-ORCH-32: El payload del reset debe contener SYSTEM_RESTORED."""
        _, _, mqtt = deps
        await orch_post_stop.reset()
        payload = mqtt.publish.call_args[0][1]
        assert payload["event"] == "SYSTEM_RESTORED"

    @pytest.mark.asyncio
    async def test_reset_payload_trigger_operator(self, orch_post_stop, deps):
        """TC-ORCH-33: El payload del reset debe indicar OPERATOR_MANUAL."""
        _, _, mqtt = deps
        await orch_post_stop.reset()
        payload = mqtt.publish.call_args[0][1]
        assert payload["trigger"] == "OPERATOR_MANUAL"

    @pytest.mark.asyncio
    async def test_reset_tiene_duration_ms_positiva(self, orch_post_stop):
        """TC-ORCH-34: El ResetResult debe tener duration_ms > 0."""
        result = await orch_post_stop.reset()
        assert result.duration_ms > 0
