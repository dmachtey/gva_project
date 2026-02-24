# GVA-07 · Sistema de Control de Emergencia

Sistema de simulación de Paro de Emergencia para Vehículo Móvil de Carga (GVA),
implementado con **Clean Architecture** en Python (backend) y HTML/JS puro (frontend).

---

## Estructura del proyecto

```
gva_project/
│
├── gva/                              ← Paquete Python (Clean Architecture)
│   ├── __init__.py                   ← API pública + factory create_gva_system()
│   ├── state_manager.py              ← Dominio: máquina de estados
│   ├── safety_orchestrator.py        ← Caso de uso: orquestador de emergencia
│   ├── motor_hal.py                  ← HAL: abstracción del relé de potencia
│   └── mqtt_comm.py                  ← Infraestructura: publicación MQTT
│
├── tests/                            ← Suite de tests unitarios
│   ├── test_state_manager.py         ← 30 tests · Capa de dominio
│   ├── test_safety_orchestrator.py   ← 34 tests · Caso de uso central
│   └── test_init.py                  ← 10 tests · API pública y factory
│
├── frontend/                         ← Aplicación web (sin dependencias externas)
│   ├── gva_panel.html                ← Panel de control GVA
│   └── gva_tester.html               ← Test runner visual en browser
│
├── conftest.py                       ← Configuración global de pytest
├── pytest.ini                        ← Opciones de ejecución
├── requirements.txt                  ← Dependencias del proyecto
└── README.md                         ← Este archivo
```

---

## Arquitectura (Clean Architecture)

```
┌──────────────────────────────────────────────────────┐
│   SafetyOrchestrator   ← Caso de Uso / Entrada       │
│   ┌────────────────────────────────────────────────┐ │
│   │   StateManager              MQTTComm           │ │  Dominio / Infraestructura
│   │   ┌──────────────────────────────────────────┐ │ │
│   │   │             MotorHAL                     │ │ │  Hardware Abstraction Layer
│   │   └──────────────────────────────────────────┘ │ │
│   └────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────┘
```

### Flujo de la Parada de Emergencia

```
[Operador] → trigger()
     │
     ├─── Paso 1/3 ──→ MotorHAL.cortar_energia()       (350ms)
     │                  └─→ Relé ABIERTO · Energía cortada
     │
     ├─── Paso 2/3 ──→ StateManager.cambiar_estado()   (300ms)
     │                  └─→ Estado: EMERGENCY_STOP
     │
     └─── Paso 3/3 ──→ MQTTComm.publish()              (400ms)
                        └─→ Publicación al broker MQTT
```

### Máquina de estados

```
NORMAL ──→ EMERGENCY_STOP ──→ RESTORING ──→ NORMAL
```

Cualquier otra transición lanza `InvalidStateTransitionError`.

---

## Instalación

### Requisitos previos

- Python 3.10 o superior
- pip

### Pasos

```bash
# 1. Descomprimir el proyecto
unzip gva_project.zip
cd gva_project

# 2. (Opcional pero recomendado) Crear entorno virtual
python3 -m venv .venv
source .venv/bin/activate        # Linux / macOS
.venv\Scripts\activate           # Windows

# 3. Instalar dependencias
pip install -r requirements.txt
```

---

## Cómo ejecutar los tests

### Ejecutar toda la suite

```bash
pytest
```

Salida esperada:

```
============================= test session starts ==============================
platform linux -- Python 3.x
collected 68 items

tests/test_state_manager.py ..............................        [ 44%]
tests/test_safety_orchestrator.py ..................................  [ 94%]
tests/test_init.py ..........                                        [100%]

============================== 68 passed in 0.5s ===============================
```

### Ejecutar con detalle (verbose)

```bash
pytest -v
```

### Ejecutar un archivo de test específico

```bash
# Solo StateManager
pytest tests/test_state_manager.py -v

# Solo SafetyOrchestrator
pytest tests/test_safety_orchestrator.py -v

# Solo __init__ y factory
pytest tests/test_init.py -v
```

### Ejecutar un test individual por nombre

```bash
pytest tests/test_state_manager.py -v -k "test_estado_inicial_es_normal"
pytest tests/test_safety_orchestrator.py -v -k "test_trigger_orden"
```

### Ejecutar con reporte de cobertura

```bash
# Instalar cobertura (si no está incluida)
pip install pytest-cov

# Correr con cobertura
pytest --cov=gva --cov-report=term-missing
```

Salida esperada:

```
----------- coverage: gva/ -----------
Name                           Stmts   Miss  Cover
--------------------------------------------------
gva/__init__.py                   28      2    93%
gva/motor_hal.py                  32      4    88%
gva/mqtt_comm.py                  24      0   100%
gva/safety_orchestrator.py        62      0   100%
gva/state_manager.py              52      0   100%
--------------------------------------------------
TOTAL                            198      6    97%
```

### Ver resultados en formato resumen

```bash
pytest --tb=short -q
```

---

## Cobertura de tests por módulo

| Archivo de test                  | Tests | Módulo testeado          | Cobertura principal                                     |
|----------------------------------|-------|--------------------------|---------------------------------------------------------|
| `test_state_manager.py`          |    30 | `state_manager.py`       | Estados, transiciones, DTO, historial, callbacks, reset |
| `test_safety_orchestrator.py`    |    34 | `safety_orchestrator.py` | Secuencia, guard clause, payload MQTT, errores, reset   |
| `test_init.py`                   |    10 | `__init__.py`            | API pública, metadatos, factory, integración e2e        |
| **Total**                        |**68** |                          | **100% passed**                                         |

---

## Uso del paquete desde Python

```python
import asyncio
import sys
sys.path.insert(0, 'gva')

from __init__ import create_gva_system

async def main():
    orch = create_gva_system(
        broker_url="mqtt://broker.gva-local:1883",
        unit_id="GVA-07",
        sector="ALMACEN-3",
    )

    result = await orch.trigger()
    print("Status:   ", result.status)
    print("HAL relay:", result.hal_result["relay"])
    print("Estado:   ", result.state_result.state)
    print("Duracion: ", result.duration_ms, "ms")

    reset_result = await orch.reset()
    print("Reset:    ", reset_result.status)

asyncio.run(main())
```

---

## Frontend (sin instalación)

Abrí directamente en el browser con doble click:

| Archivo                      | Descripción                                                       |
|------------------------------|-------------------------------------------------------------------|
| `frontend/gva_panel.html`    | Panel de control con botón de emergencia, LED, estado y logs MQTT |
| `frontend/gva_tester.html`   | Test runner visual con 16 casos de prueba ejecutándose en vivo    |

---

## Solución de problemas

**`ModuleNotFoundError: No module named 'pytest_asyncio'`**
```bash
pip install pytest-asyncio
```

**`ModuleNotFoundError: No module named 'state_manager'`**
```bash
# Asegurarse de correr pytest desde la raíz del proyecto
cd gva_project
pytest
```

**Los tests tardan mucho**

Los delays reales (300-400ms) están mockeados con `AsyncMock` en los tests,
por lo que la suite completa debe correr en menos de 1 segundo.
Si tardara más, verificar que `pytest-asyncio` esté instalado correctamente.
