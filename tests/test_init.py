"""
test_init.py
============
Tests para el paquete GVA — verifica la API pública expuesta
en __init__.py y el correcto funcionamiento de la factory
create_gva_system().

Ejecutar:
    pytest test_init.py -v
"""

import pytest
import pytest_asyncio
from unittest.mock import patch, AsyncMock, MagicMock
import os

import importlib
import state_manager as sm_module
import safety_orchestrator as orch_module
import motor_hal as hal_module
import mqtt_comm as mqtt_module

# Importar símbolos directamente desde los módulos fuente
from state_manager import (
    StateManager, SystemState, StateChangeResult,
    InvalidStateTransitionError, VALID_TRANSITIONS,
)
from safety_orchestrator import (
    SafetyOrchestrator, EmergencyStopResult, ResetResult,
    OrchestratorBusyError, EmergencyStopFailedError,
)
from motor_hal import MotorHAL, RelayState
from mqtt_comm  import MQTTComm, MQTTResult


# ══════════════════════════════════════════════════════════════════
#  SUITE 1 — API pública exportada
# ══════════════════════════════════════════════════════════════════

class TestApiPublica:
    """Verifica que todos los símbolos declarados en __all__ son importables."""

    def test_state_manager_importable(self):
        """TC-INIT-01: StateManager debe estar disponible."""
        assert StateManager is not None

    def test_system_state_importable(self):
        """TC-INIT-02: SystemState debe estar disponible."""
        assert SystemState is not None

    def test_state_change_result_importable(self):
        """TC-INIT-03: StateChangeResult debe estar disponible."""
        assert StateChangeResult is not None

    def test_invalid_state_transition_error_importable(self):
        """TC-INIT-04: InvalidStateTransitionError debe estar disponible."""
        assert InvalidStateTransitionError is not None

    def test_valid_transitions_importable(self):
        """TC-INIT-05: VALID_TRANSITIONS debe estar disponible."""
        assert VALID_TRANSITIONS is not None

    def test_safety_orchestrator_importable(self):
        """TC-INIT-06: SafetyOrchestrator debe estar disponible."""
        assert SafetyOrchestrator is not None

    def test_emergency_stop_result_importable(self):
        """TC-INIT-07: EmergencyStopResult debe estar disponible."""
        assert EmergencyStopResult is not None

    def test_reset_result_importable(self):
        """TC-INIT-08: ResetResult debe estar disponible."""
        assert ResetResult is not None

    def test_orchestrator_busy_error_importable(self):
        """TC-INIT-09: OrchestratorBusyError debe estar disponible."""
        assert OrchestratorBusyError is not None

    def test_emergency_stop_failed_error_importable(self):
        """TC-INIT-10: EmergencyStopFailedError debe estar disponible."""
        assert EmergencyStopFailedError is not None

    def test_motor_hal_importable(self):
        """TC-INIT-11: MotorHAL debe estar disponible."""
        assert MotorHAL is not None

    def test_relay_state_importable(self):
        """TC-INIT-12: RelayState debe estar disponible."""
        assert RelayState is not None

    def test_mqtt_comm_importable(self):
        """TC-INIT-13: MQTTComm debe estar disponible."""
        assert MQTTComm is not None

    def test_mqtt_result_importable(self):
        """TC-INIT-14: MQTTResult debe estar disponible."""
        assert MQTTResult is not None


# ══════════════════════════════════════════════════════════════════
#  SUITE 2 — Metadatos del paquete
# ══════════════════════════════════════════════════════════════════

class TestMetadatos:
    """Verifica las constantes de versión y configuración del paquete."""

    def _get_init_module(self):
        import importlib.util
        init_path = os.path.join(os.path.dirname(__file__), '..', 'gva', '__init__.py')
        spec = importlib.util.spec_from_file_location("gva_init", init_path)
        mod  = importlib.util.module_from_spec(spec)
        # patch imports para evitar dependencias circulares en el test
        with patch.dict('sys.modules', {
            'state_manager':       sm_module,
            'safety_orchestrator': orch_module,
            'motor_hal':           hal_module,
            'mqtt_comm':           mqtt_module,
        }):
            spec.loader.exec_module(mod)
        return mod

    def test_version_definida(self):
        """TC-INIT-15: __version__ debe estar definida y ser string."""
        mod = self._get_init_module()
        assert isinstance(mod.__version__, str)
        assert len(mod.__version__) > 0

    def test_version_formato_semver(self):
        """TC-INIT-16: __version__ debe seguir formato semver X.Y.Z."""
        mod = self._get_init_module()
        partes = mod.__version__.split(".")
        assert len(partes) == 3
        assert all(p.isdigit() for p in partes)

    def test_unit_id_definido(self):
        """TC-INIT-17: __unit__ debe ser 'GVA-07'."""
        mod = self._get_init_module()
        assert mod.__unit__ == "GVA-07"

    def test_sector_definido(self):
        """TC-INIT-18: __sector__ debe ser 'ALMACÉN-3'."""
        mod = self._get_init_module()
        assert mod.__sector__ == "ALMACÉN-3"

    def test_author_definido(self):
        """TC-INIT-19: __author__ debe estar definido."""
        mod = self._get_init_module()
        assert isinstance(mod.__author__, str)
        assert len(mod.__author__) > 0


# ══════════════════════════════════════════════════════════════════
#  SUITE 3 — Factory create_gva_system()
# ══════════════════════════════════════════════════════════════════

class TestFactory:
    """Verifica la factory helper que construye el sistema completo."""

    def _get_factory(self):
        import importlib.util
        init_path = os.path.join(os.path.dirname(__file__), '..', 'gva', '__init__.py')
        spec = importlib.util.spec_from_file_location("gva_init", init_path)
        mod  = importlib.util.module_from_spec(spec)
        with patch.dict('sys.modules', {
            'state_manager':       sm_module,
            'safety_orchestrator': orch_module,
            'motor_hal':           hal_module,
            'mqtt_comm':           mqtt_module,
        }):
            spec.loader.exec_module(mod)
        return mod.create_gva_system

    def test_factory_retorna_safety_orchestrator(self):
        """TC-INIT-20: create_gva_system() debe retornar un SafetyOrchestrator."""
        factory = self._get_factory()
        orch = factory()
        assert isinstance(orch, SafetyOrchestrator)

    def test_factory_is_running_false_al_inicio(self):
        """TC-INIT-21: El orquestador creado debe tener is_running=False."""
        factory = self._get_factory()
        orch = factory()
        assert orch.is_running is False

    def test_factory_last_result_none_al_inicio(self):
        """TC-INIT-22: El orquestador creado debe tener last_result=None."""
        factory = self._get_factory()
        orch = factory()
        assert orch.last_result is None

    def test_factory_acepta_broker_url_personalizado(self):
        """TC-INIT-23: La factory debe aceptar broker_url personalizado."""
        factory = self._get_factory()
        orch = factory(broker_url="mqtt://custom-broker:1883")
        assert isinstance(orch, SafetyOrchestrator)

    def test_factory_acepta_unit_id_personalizado(self):
        """TC-INIT-24: La factory debe aceptar unit_id personalizado."""
        factory = self._get_factory()
        orch = factory(unit_id="GVA-99")
        assert isinstance(orch, SafetyOrchestrator)

    def test_factory_acepta_sector_personalizado(self):
        """TC-INIT-25: La factory debe aceptar sector personalizado."""
        factory = self._get_factory()
        orch = factory(sector="ALMACÉN-7")
        assert isinstance(orch, SafetyOrchestrator)

    def test_factory_crea_instancias_independientes(self):
        """TC-INIT-26: Dos llamadas a la factory deben crear instancias distintas."""
        factory = self._get_factory()
        orch1 = factory()
        orch2 = factory()
        assert orch1 is not orch2


# ══════════════════════════════════════════════════════════════════
#  SUITE 4 — Integración superficial (sin mocks)
# ══════════════════════════════════════════════════════════════════

class TestIntegracionSuperficial:
    """
    Tests de smoke que verifican que los módulos colaboran correctamente
    cuando se instancian con sus implementaciones reales (sin mocks),
    pero con delays anulados vía monkeypatching de asyncio.sleep.
    """

    @pytest.mark.asyncio
    async def test_state_manager_real_transicion_emergency(self):
        """TC-INIT-27: StateManager real puede transicionar a EMERGENCY_STOP."""
        with patch("asyncio.sleep", new_callable=AsyncMock):
            m = StateManager()
            result = await m.cambiar_estado(SystemState.EMERGENCY_STOP)
        assert result.status == "OK"
        assert m.current_state == SystemState.EMERGENCY_STOP

    @pytest.mark.asyncio
    async def test_motor_hal_real_cortar_energia(self):
        """TC-INIT-28: MotorHAL real puede cortar la energía."""
        with patch("asyncio.sleep", new_callable=AsyncMock):
            hal = MotorHAL()
            result = await hal.cortar_energia()
        assert result["status"] == "OK"
        assert result["relay"] == "OPEN"

    @pytest.mark.asyncio
    async def test_mqtt_comm_real_publish(self):
        """TC-INIT-29: MQTTComm real puede publicar un mensaje."""
        with patch("asyncio.sleep", new_callable=AsyncMock):
            mqtt = MQTTComm()
            result = await mqtt.publish("test/topic", {"event": "TEST"})
        assert result["status"] == "OK"
        assert result["topic"] == "test/topic"

    @pytest.mark.asyncio
    async def test_sistema_completo_trigger_con_delays_anulados(self):
        """TC-INIT-30: Sistema completo ejecuta trigger() con delays=0."""
        with patch("asyncio.sleep", new_callable=AsyncMock):
            hal   = MotorHAL()
            state = StateManager()
            mqtt  = MQTTComm()
            orch  = SafetyOrchestrator(hal, state, mqtt)
            result = await orch.trigger()

        assert result.status == "OK"
        assert result.hal_result["relay"] == "OPEN"
        assert result.state_result.state == SystemState.EMERGENCY_STOP
        assert state.current_state == SystemState.EMERGENCY_STOP
        assert orch.is_running is True
