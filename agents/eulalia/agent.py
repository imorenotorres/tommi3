"""
Eulalia — Tutor virtual de Lingüística Aplicada a la Logopedia.

Agente concreto que hereda de BaseTutorFonetica.
Toda la maquinaria de transcripción, ejercicios y corrección
viene de la plantilla base (tutor_fonetica_base/).

Este módulo solo necesita definir _AGENT_FILE y, opcionalmente,
sobrescribir métodos para personalizar el comportamiento.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tutor_fonetica_base.base_tutor import BaseTutorFonetica


class Agent(BaseTutorFonetica):
    _AGENT_FILE = __file__
