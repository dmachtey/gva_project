# conftest.py — Configuración global de pytest
import sys
import os

# Agrega el paquete gva al path para que los tests lo encuentren
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'gva'))
