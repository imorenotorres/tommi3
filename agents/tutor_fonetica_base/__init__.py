"""
Plantilla base para tutores virtuales de Fonética.

Proporciona:
  - Transcripción fonológica/fonética programática
  - Motor de ejercicios (transcripción y errores fonológicos)
  - Gestión de progreso del alumno
  - Gestión de usuarios por asignatura
  - Base de conocimiento BM25 (vectorless RAG)

Cada asignatura concreta hereda de BaseTutorFonetica y añade
su propio config.json, prompts.json, data/docs/ y users.json.
"""
