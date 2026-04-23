#!/usr/bin/env python3
"""
Benchmark de Pisha3 - Script para pruebas de rendimiento

Ejecuta un paquete de preguntas predefinidas y genera un log con:
- Tiempos de cada fase (schema, text_to_sql, execute, format)
- SQL generado para cada pregunta
- Resultados y errores

Uso:
    python benchmark.py -q          # Ejecutar todas las preguntas
    python benchmark.py -q 10       # Ejecutar solo 10 preguntas
    python benchmark.py -s          # Ejecutar todos los escenarios
    python benchmark.py -s 5        # Ejecutar solo 5 escenarios
    python benchmark.py --all       # Ejecutar todo (preguntas + escenarios)
    python benchmark.py -q -s       # Ejecutar todas las preguntas y escenarios
    python benchmark.py --help      # Mostrar ayuda
"""

# Activar venv automáticamente si no está activo
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "apps"))
from venv_helper import ensure_venv
ensure_venv()

import os
import json
import argparse
import statistics
from datetime import datetime

# Cargar variables de entorno desde .env ANTES de importar el agente
def load_env_file(env_path: str) -> None:
    """Carga variables de entorno desde un archivo .env (sin dependencia de python-dotenv)."""
    if not os.path.exists(env_path):
        return
    with open(env_path, "r") as f:
        for line in f:
            line = line.strip()
            # Ignorar comentarios y líneas vacías
            if not line or line.startswith("#"):
                continue
            # Parsear KEY=value
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                # Eliminar comillas si las hay
                if value and value[0] in ('"', "'") and value[-1] == value[0]:
                    value = value[1:-1]
                os.environ[key] = value

env_path = os.path.join(os.path.dirname(__file__), ".env")
load_env_file(env_path)

# Añadir el directorio actual al path
sys.path.insert(0, os.path.dirname(__file__))

from agent import Agent

# ============================================================================
# PAQUETE DE PREGUNTAS DE PRUEBA
# ============================================================================

PREGUNTAS_BENCHMARK = [
    # --- Búsqueda por país --- La primera se repite por si hay warm-up
    "¿Qué destinos hay disponibles en Alemania?",
    "¿Qué destinos hay disponibles en Alemania?",
    "¿A qué universidades puedo ir en Italia?",
    "¿Hay convenios con Francia?",
    "¿Cuántos destinos hay en América Latina?",
    "¿Tenemos convenios Erasmus con países de Ásia?",

    # --- Búsqueda por facultad/titulación ---
    "¿Qué destinos hay para estudiantes de la Facultad de Derecho?",
    "¿A dónde puedo ir si estudio Ingeniería Informática?",
    "¿Qué opciones de movilidad tiene la Facultad de Medicina?",

    # --- Búsqueda por programa ---
    "¿Qué destinos hay con ERASMUS+ KA131?",
    "¿Cuáles son las opciones de MOVILIDAD INTERNACIONAL UMA?",
    "¿Qué universidades participan en el programa ISEP?",

    # --- Requisitos de idioma ---
    "¿Qué destinos no requieren acreditación de idioma?",
    "¿Qué nivel de inglés necesito para ir a Alemania?",
    "¿Hay destinos donde se requiera solo B1 de inglés?",
    "¿Hay destinos en Europa que no requieran idioma?",

    # --- Plazas y disponibilidad ---
    "¿Qué destinos tienen plazas disponibles?",
    "¿Cuántas plazas hay para el primer cuatrimestre en universidades de Finlandia?",

    # --- Consultas complejas (una sola tabla) ---
    "¿Cuántas plazas en universidades de Finlandia en las que el nivel de inglés sea B1?",
    "¿Qué universidades de Europa tienen convenio con la Facultad de Ciencias en los que el nivel de inglés es B1?",
    "¿Hay algún convenio en alemania que pida nivel de alemán B2 para la Facultad de Filosofía y Letras?",
    "¿Con qué paises de América latina tiene convenios la Facultad de Medicina?",

    # --- Consultas específicas ---
    "¿Qué acuerdos hay con The Hague University of Applied Sciences?",
    "¿Hay convenios con universidades de Rumanía?",

    # --- Consultas con combinación de criterios avanzados ---
    "¿Qué destinos hay disponibles en Italia para grado de enfermería que no requieran título de idioma?",
    "¿Qué nivel de idioma se necesita para estudiar arquitectura en la universidad de La Sapienza?",
    "¿Hace falta una nota media mínima para poder estudiar en la universidad de Berlín?",

    # --- Consultas sobre estudiantes ---
    "¿Cuántos estudiantes hay matriculados?",
    "Busca al estudiante Russell Ryan",
    "¿Qué estudiantes tienen email que termine en @uma.es?",

    # --- Consultas sobre titulaciones ---
    "¿Cuántas titulaciones hay en la UMA?",
    "¿Qué titulaciones hay?",
    "¿Existe el grado en Informática?",

    # --- Consultas sobre asignaturas ---
    "¿Cuántas asignaturas hay en total?",
    "¿Qué asignaturas tiene el grado en Derecho?",
    "¿Qué asignaturas de tercer curso tiene el grado en Medicina?",
    "¿Cuántas asignaturas optativas tiene Informática?",

    # --- Consultas cross-table (asignaturas + titulaciones) ---
    "¿Cuántas asignaturas tiene cada titulación?",
    "¿Qué asignaturas de primer curso tiene Arquitectura?",

    # --- Consultas multi-tabla (destinos + titulaciones/asignaturas/estudiantes) ---
    # Estudiante real + destinos para su titulación en un país
    "Soy Russell Ryan, estudiante de Arquitectura. ¿A qué universidades de Italia puedo ir de Erasmus?",
    # Asignaturas de una titulación + destinos disponibles
    "¿Cuántas asignaturas tiene el grado en Arquitectura y cuántos destinos hay en Italia para esa titulación?",
    # Verificar existencia de estudiante + destinos para titulación
    "¿Existe el estudiante Charles Williams? Si es así, dime qué destinos hay en Alemania para Ingeniería Informática.",
    # Destinos + info de asignaturas de la titulación
    "¿Qué destinos Erasmus hay para Medicina en Chile y cuántas asignaturas de tercer curso tiene esa titulación?",
    # Titulaciones con destinos en un país + número de asignaturas
    "¿Qué titulaciones de la UMA tienen convenios con universidades de Corea del Sur?",
    # Estudiante + idioma requerido en destino
    "Soy Stephanie Smith, estudio Enfermería. ¿Qué nivel de inglés necesito para ir a Finlandia?",
    # Asignaturas optativas + destinos internacionales
    "¿Cuántas asignaturas optativas tiene Derecho y qué destinos hay en Francia para esa titulación?",
    # Número de estudiantes + número de destinos por programa
    "¿Cuántos estudiantes hay matriculados y cuántos destinos Erasmus+ KA131 tiene la UMA?",
    # Buscar estudiante + verificar si destino admite grado
    "Busca al estudiante Andrew Schwartz. Si estudiara Arquitectura, ¿podría ir a la Sapienza University of Rome?",
    # Asignaturas de primer curso + destinos para esa titulación sin requisito de idioma
    "¿Qué asignaturas de primer curso tiene Ingeniería Informática y qué destinos hay sin requisito de idioma para esa titulación?",

    # --- Consultas con múltiples criterios (análisis de causas) ---
    # 2 criterios - combinación que no existe
    "¿Hay convenios en Japón que requieran coreano B2?",
    "¿Por qué no hay plazas con alemán B1 en Corea del Sur?",
    # 2 criterios - criterio individual inexistente
    "¿Hay convenios en Finlandia que pidan francés B2?",
    # 3 criterios - todas las combinaciones de pares existen pero no la total
    "¿Hay plazas en Alemania para Medicina que pidan inglés C1?",
    # 3 criterios - alguna combinación de pares falla
    "¿Hay convenios en Alemania para Derecho que pidan francés B2?",
    # 3 criterios con plazas disponibles
    "¿Hay plazas disponibles en Italia para la Facultad de Ciencias con inglés B2?",
]

PREGUNTAS_QUICK = [
    "¿Qué destinos hay en Alemania?",
    "¿Cuántos convenios hay en Francia?",
    "¿Hay destinos sin requisito de idioma?",
    "¿Qué universidades tienen plazas Erasmus?",
    "¿Qué opciones hay para Derecho?",
    "¿Cuántos estudiantes hay?",
    "¿Qué asignaturas tiene Informática?",
    "¿Cuántas titulaciones hay?",
]

# Preguntas específicas de idiomas (para benchmark --idiomas)
PREGUNTAS_IDIOMAS = [
    # Warm-up
    "¿Qué destinos no requieren acreditación de idioma?",
    # Preguntas de idiomas
    "¿Qué destinos no requieren acreditación de idioma?",
    "¿Qué nivel de inglés necesito para ir a Alemania?",
    "¿Hay destinos donde se requiera solo B1 de inglés?",
    "¿Hay destinos en Europa que no requieran idioma?",
    "¿Qué nivel de idioma se necesita para estudiar arquitectura en la universidad de La Sapienza?",
    "¿Hay algún convenio en alemania que pida nivel de alemán B2 para la Facultad de Filosofía y Letras?",
    "¿Cuántas plazas en universidades de Finlandia en las que el nivel de inglés sea B1?",
    "¿Hay convenios en Finlandia que pidan francés B2?",
    "¿Hay plazas en Alemania para Medicina que pidan inglés C1?",
]

# ============================================================================
# PREGUNTAS EXTRACOMPLEJAS (errores ortográficos, criterios adicionales, regiones)
# Se asume que algún fallo es normal en esta sección
# ============================================================================

PREGUNTAS_EXTRACOMPLEJAS = [
    # --- Con errores ortográficos, gramaticales o de estilo ---
    # 1. Falta de tildes y minúsculas
    "que universidades hay en belgica para erasmus?",
    # 2. Error ortográfico en país
    "¿Hay convenios con Finlandia o Noruega para ingenieria informatica?",
    # 3. Estilo coloquial/informal
    "oye, donde puedo ir si hago derecho y quiero ir a sitios que no pidan mucho idioma?",
    # 4. Mezcla de mayúsculas y errores
    "QUIERO IR A ALEMANIA con nivel b1 de aleman, hay plazas?",
    # 5. Abreviaturas y estilo SMS
    "q unis hay en italia pa medicina?",
    # 6. Pregunta mal estructurada
    "plazas italia ciencias inglés B2 hay?",
    # 7. Errores múltiples + región
    "convenios en paises nordicos sin requisito de idioma para filosofia y letras",

    # --- Con criterios adicionales (3-4 criterios) ---
    # 8. País + facultad + idioma + nivel específico
    "¿Hay convenios en Francia para Económicas que pidan francés B2 y tengan plazas en el primer cuatrimestre?",
    # 9. Región + programa + facultad + idioma
    "¿Qué universidades de Europa del Este tienen programa Erasmus para Derecho con inglés B1?",
    # 10. País + múltiples facultades + idioma
    "¿Hay destinos en Alemania para estudiantes de Ciencias o Ingeniería que requieran alemán?",
    # 11. Grupo de países + programa + plazas + cuatrimestre
    "¿Cuántas plazas Erasmus hay en países nórdicos para el segundo cuatrimestre?",
    # 12. País + facultad + idioma + nivel + plazas disponibles
    "Universidades en Portugal para Turismo con portugués B1 y plazas disponibles",
    # 13. Región + sin idioma + facultad específica + programa
    "¿Hay convenios ISEP en Latinoamérica para Medicina sin requisito de idioma?",
    # 14. Múltiples países específicos + facultad + idioma
    "¿Qué opciones hay en Alemania, Austria o Suiza para Filosofía con alemán B2?",

    # --- Con regiones o grupos de países ---
    # 15. Países escandinavos
    "¿Qué convenios hay con los países escandinavos para cualquier facultad?",
    # 16. Europa del Este
    "¿Hay destinos en Europa del Este que no requieran idioma?",
    # 17. Países de habla inglesa
    "¿Qué universidades hay en países de habla inglesa con plazas disponibles?",
    # 18. Unión Europea vs no UE
    "¿Hay convenios fuera de la Unión Europea para Ingeniería?",
    # 19. Países mediterráneos
    "Destinos en países mediterráneos con Erasmus+ para Turismo",
    # 20. Países germánicos
    "¿Qué opciones de movilidad hay en países de habla alemana para Económicas?",
    # 21. Benelux
    "¿Hay plazas en el Benelux para estudiantes de Derecho con inglés o francés?",

    # --- Nuevas frases
    # 22.  
    "¿Qué destinos hay disponibles en Italia para grado de enfermería que no requieran título de idioma?",
    # 23.  
     "¿Qué nivel de idioma se necesita para estudiar arquitectura en la universidad de La Sapienza?",
    # 24.
    "¿Hace falta una nota media mínima para poder estudiar en la universidad de Berlín?",
    # 25.
    "¿Hay convenios en Japón que requieran coreano B2?",
    # 26.
    "¿Por qué no hay plazas con alemán B1 en Corea del Sur?",

    # --- Preguntas sobre estudiantes (con errores/estilo informal) ---
    # 27. Búsqueda informal de estudiante
    "busca a un estudiante que se llame Smith",
    # 28. Consulta coloquial sobre asignaturas
    "q asignaturas tiene informatica de segundo?",
    # 29. Cross-table con errores
    "cuantas optativas tiene el grado de biologia?",
    # 30. Pregunta en inglés sobre estudiantes
    "How many students are enrolled?",
    # 31. Búsqueda cruzada destinos + titulaciones
    "¿Qué destinos Erasmus hay para estudiantes de Administración y Dirección de Empresas?",

    # --- Preguntas multi-tabla con errores/estilo informal ---
    # 32. Multi-tabla informal: estudiante + destinos
    "oye busca a Brady Brown, estudia arquitectura en la UMA y quiere irse de erasmus a italia, que opciones tiene?",
    # 33. Multi-tabla con errores: asignaturas + destinos
    "cuantas asignaturas tiene medicina y cuantos destinos hay en chile pa esa carrera?",
    # 34. Multi-tabla en inglés
    "Find student Michele Graham and show me destinations in Korea for Architecture",
    # 35. Multi-tabla SMS style
    "q destinos hay en alemania pa informatica y cuantas asignaturas optativas tiene?",
    # 36. Multi-tabla coloquial: nota media + destino
    "necesito nota media pa ir a la universidad de filipinas si estudio arquitectura?",
]

# ============================================================================
# RESPUESTAS SQL DE REFERENCIA (extraídas de logs/loop_mistral-large_20260228_202655.log)
# ============================================================================

RESPUESTAS_REFERENCIA = {
    "¿Qué destinos hay disponibles en Alemania?": "SELECT * FROM destinations WHERE destination_country LIKE '%Alemania%'",
    "¿A qué universidades puedo ir en Italia?": "SELECT host_institution FROM destinations WHERE destination_country LIKE '%Italia%'",
    "¿Hay convenios con Francia?": "SELECT * FROM destinations WHERE destination_country LIKE '%Francia%'",
    "¿Cuántos destinos hay en América Latina?": "SELECT COUNT(*) FROM destinations WHERE destination_country IN ('Argentina', 'Bolivia', 'Brasil', 'Chile', 'Colombia', 'Costa Rica', 'Ecuador', 'Honduras', 'México', 'Panamá', 'Paraguay', 'Perú', 'Puerto Rico', 'República Dominicana', 'Uruguay', 'Venezuela')",
    "¿Tenemos convenios Erasmus con países de Ásia?": "SELECT DISTINCT host_institution, destination_country FROM destinations WHERE mobility_program LIKE '%ERASMUS%' AND destination_country IN ('Armenia', 'Corea del Sur', 'Filipinas', 'India', 'Indonesia', 'Japón', 'Kazajistán', 'Malasia', 'Nepal', 'Tailandia', 'Taiwán')",
    "¿Qué destinos hay para estudiantes de la Facultad de Derecho?": "SELECT * FROM destinations WHERE uma_faculties LIKE '%Derecho%'",
    "¿A dónde puedo ir si estudio Ingeniería Informática?": "SELECT host_institution, destination_country, mobility_program, student_vacancies, lang_1_name, lang_1_level FROM destinations WHERE uma_degrees LIKE '%Ingeniería Informática%'",
    "¿Qué opciones de movilidad tiene la Facultad de Medicina?": "SELECT * FROM destinations WHERE uma_faculties LIKE '%Medicina%'",
    "¿Qué destinos hay con ERASMUS+ KA131?": "SELECT * FROM destinations WHERE mobility_program LIKE '%ERASMUS+ KA131%'",
    "¿Cuáles son las opciones de MOVILIDAD INTERNACIONAL UMA?": "SELECT * FROM destinations WHERE mobility_program LIKE '%MOVILIDAD INTERNACIONAL UMA%'",
    "¿Qué universidades participan en el programa ISEP?": "SELECT host_institution FROM destinations WHERE mobility_program LIKE '%ISEP%'",
    "¿Qué destinos no requieren acreditación de idioma?": "SELECT * FROM destinations WHERE lang_1_name IS NULL",
    "¿Qué nivel de inglés necesito para ir a Alemania?": "SELECT lang_1_name, lang_1_level, lang_2_name, lang_2_level FROM destinations WHERE destination_country LIKE '%Alemania%' AND (lang_1_name LIKE '%Inglés%' OR lang_2_name LIKE '%Inglés%')",
    "¿Hay destinos donde se requiera solo B1 de inglés?": "SELECT * FROM destinations WHERE ((lang_1_name LIKE '%Inglés%' AND lang_1_level = 'B1') OR (lang_2_name LIKE '%Inglés%' AND lang_2_level = 'B1')) AND NOT (lang_1_level IN ('B2','C1','C2') OR lang_2_level IN ('B2','C1','C2'))",
    "¿Hay destinos en Europa que no requieran idioma?": "SELECT * FROM destinations WHERE destination_country IN ('Albania', 'Alemania', 'Austria', 'Bélgica', 'Bulgaria', 'República Checa', 'Croacia', 'Dinamarca', 'Eslovaquia', 'Eslovenia', 'España', 'Estonia', 'Finlandia', 'Francia', 'Georgia', 'Grecia', 'Hungría', 'Irlanda', 'Islandia', 'Italia', 'Letonia', 'Lituania', 'Malta', 'Moldavia', 'Noruega', 'Países Bajos', 'Polonia', 'Portugal', 'Reino Unido', 'República de Chipre', 'República de Macedonia', 'Rumanía', 'Serbia', 'Suecia', 'Suiza', 'Turquía', 'Ucrania') AND lang_1_name IS NULL",
    "¿Qué destinos tienen plazas disponibles?": "SELECT * FROM destinations WHERE student_vacancies NOT LIKE '%Plazas: 0%'",
    "¿Cuántas plazas hay para el primer cuatrimestre en universidades de Finlandia?": "SELECT COUNT(*) FROM destinations WHERE destination_country LIKE '%Finlandia%' AND student_vacancies LIKE '%1er CUATRIMESTRE%' AND student_vacancies NOT LIKE '%Plazas: 0%'",
    "¿Cuántas plazas en universidades de Finlandia en las que el nivel de inglés sea B1?": "SELECT COUNT(*) FROM destinations WHERE destination_country LIKE '%Finlandia%' AND ((lang_1_name LIKE '%Inglés%' AND lang_1_level = 'B1') OR (lang_2_name LIKE '%Inglés%' AND lang_2_level = 'B1')) AND student_vacancies NOT LIKE '%Plazas: 0%'",
    "¿Qué universidades de Europa tienen convenio con la Facultad de Ciencias en los que el nivel de inglés es B1?": "SELECT host_institution, destination_country FROM destinations WHERE destination_country IN ('Albania', 'Alemania', 'Austria', 'Bélgica', 'Bulgaria', 'República Checa', 'Croacia', 'Dinamarca', 'Eslovaquia', 'Eslovenia', 'España', 'Estonia', 'Finlandia', 'Francia', 'Georgia', 'Grecia', 'Hungría', 'Irlanda', 'Islandia', 'Italia', 'Letonia', 'Lituania', 'Malta', 'Moldavia', 'Noruega', 'Países Bajos', 'Polonia', 'Portugal', 'Reino Unido', 'República de Chipre', 'República de Macedonia', 'Rumanía', 'Serbia', 'Suecia', 'Suiza', 'Turquía', 'Ucrania') AND uma_faculties LIKE '%Ciencias%' AND ((lang_1_name LIKE '%Inglés%' AND lang_1_level = 'B1') OR (lang_2_name LIKE '%Inglés%' AND lang_2_level = 'B1'))",
    "¿Hay algún convenio en alemania que pida nivel de alemán B2 para la Facultad de Filosofía y Letras?": "SELECT * FROM destinations WHERE destination_country LIKE '%Alemania%' AND ((lang_1_name LIKE '%Alemán%' AND lang_1_level = 'B2') OR (lang_2_name LIKE '%Alemán%' AND lang_2_level = 'B2')) AND uma_faculties LIKE '%Filosofía y Letras%'",
    "¿Con qué paises de América latina tiene convenios la Facultad de Medicina?": "SELECT DISTINCT destination_country FROM destinations WHERE destination_country IN ('Argentina', 'Bolivia', 'Brasil', 'Chile', 'Colombia', 'Costa Rica', 'Ecuador', 'Honduras', 'México', 'Panamá', 'Paraguay', 'Perú', 'Puerto Rico', 'República Dominicana', 'Uruguay', 'Venezuela') AND uma_faculties LIKE '%Medicina%'",
    "¿Qué acuerdos hay con The Hague University of Applied Sciences?": "SELECT * FROM destinations WHERE host_institution LIKE '%The Hague University of Applied Sciences%'",
    "¿Hay convenios con universidades de Rumanía?": "SELECT * FROM destinations WHERE destination_country LIKE '%Rumanía%'",
    # Consultas nuevas (combinación de criterios avanzados)
    "¿Qué destinos hay disponibles en Italia para grado de enfermería que no requieran título de idioma?": "SELECT * FROM destinations WHERE destination_country LIKE '%Italia%' AND uma_degrees LIKE '%Enfermería%' AND lang_1_name IS NULL",
    "¿Qué nivel de idioma se necesita para estudiar arquitectura en la universidad de La Sapienza?": "SELECT lang_1_name, lang_1_level, lang_2_name, lang_2_level FROM destinations WHERE host_institution LIKE '%La Sapienza%' AND uma_degrees LIKE '%Arquitectura%'",
    "¿Hace falta una nota media mínima para poder estudiar en la universidad de Berlín?": "SELECT host_institution, academic_requirements_text FROM destinations WHERE host_institution LIKE '%Berlín%' OR host_institution LIKE '%Berlin%'",
    # Consultas con múltiples criterios (análisis de causas)
    "¿Hay convenios en Japón que requieran coreano B2?": "SELECT * FROM destinations WHERE destination_country LIKE '%Japón%' AND ((lang_1_name LIKE '%Coreano%' AND lang_1_level = 'B2') OR (lang_2_name LIKE '%Coreano%' AND lang_2_level = 'B2'))",
    "¿Por qué no hay plazas con alemán B1 en Corea del Sur?": "SELECT * FROM destinations WHERE destination_country LIKE '%Corea del Sur%' AND ((lang_1_name LIKE '%Alemán%' AND lang_1_level = 'B1') OR (lang_2_name LIKE '%Alemán%' AND lang_2_level = 'B1')) AND student_vacancies NOT LIKE '%Plazas: 0%'",
    "¿Hay convenios en Finlandia que pidan francés B2?": "SELECT * FROM destinations WHERE destination_country LIKE '%Finlandia%' AND ((lang_1_name LIKE '%Francés%' AND lang_1_level = 'B2') OR (lang_2_name LIKE '%Francés%' AND lang_2_level = 'B2'))",
    "¿Hay plazas en Alemania para Medicina que pidan inglés C1?": "SELECT * FROM destinations WHERE destination_country LIKE '%Alemania%' AND uma_faculties LIKE '%Medicina%' AND ((lang_1_name LIKE '%Inglés%' AND lang_1_level = 'C1') OR (lang_2_name LIKE '%Inglés%' AND lang_2_level = 'C1')) AND student_vacancies NOT LIKE '%Plazas: 0%'",
    "¿Hay convenios en Alemania para Derecho que pidan francés B2?": "SELECT * FROM destinations WHERE destination_country LIKE '%Alemania%' AND uma_faculties LIKE '%Derecho%' AND ((lang_1_name LIKE '%Francés%' AND lang_1_level = 'B2') OR (lang_2_name LIKE '%Francés%' AND lang_2_level = 'B2'))",
    "¿Hay plazas disponibles en Italia para la Facultad de Ciencias con inglés B2?": "SELECT * FROM destinations WHERE destination_country LIKE '%Italia%' AND uma_faculties LIKE '%Ciencias%' AND ((lang_1_name LIKE '%Inglés%' AND lang_1_level = 'B2') OR (lang_2_name LIKE '%Inglés%' AND lang_2_level = 'B2')) AND student_vacancies NOT LIKE '%Plazas: 0%'",

    # --- RESPUESTAS ESTUDIANTES ---
    "¿Cuántos estudiantes hay matriculados?": "SELECT COUNT(*) FROM students",
    "Busca al estudiante Russell Ryan": "SELECT * FROM students WHERE name LIKE '%Russell Ryan%'",
    "¿Qué estudiantes tienen email que termine en @uma.es?": "SELECT * FROM students WHERE email LIKE '%@uma.es'",

    # --- RESPUESTAS TITULACIONES ---
    "¿Cuántas titulaciones hay en la UMA?": "SELECT COUNT(*) FROM degree",
    "¿Qué titulaciones hay?": "SELECT * FROM degree",
    "¿Existe el grado en Informática?": "SELECT * FROM degree WHERE name LIKE '%Informática%'",

    # --- RESPUESTAS ASIGNATURAS ---
    "¿Cuántas asignaturas hay en total?": "SELECT COUNT(*) FROM subjects",
    "¿Qué asignaturas tiene el grado en Derecho?": "SELECT s.* FROM subjects s JOIN degree d ON s.degree_id = d.id WHERE d.name LIKE '%Derecho%'",
    "¿Qué asignaturas de tercer curso tiene el grado en Medicina?": "SELECT s.* FROM subjects s JOIN degree d ON s.degree_id = d.id WHERE d.name LIKE '%Medicina%' AND s.subject_code LIKE '3%'",
    "¿Cuántas asignaturas optativas tiene Informática?": "SELECT COUNT(*) FROM subjects s JOIN degree d ON s.degree_id = d.id WHERE d.name LIKE '%Informática%' AND (s.subject_code LIKE '8%' OR s.subject_code LIKE '9%')",

    # --- RESPUESTAS CROSS-TABLE ---
    "¿Cuántas asignaturas tiene cada titulación?": "SELECT d.name, COUNT(*) FROM subjects s JOIN degree d ON s.degree_id = d.id GROUP BY d.name",
    "¿Qué asignaturas de primer curso tiene Arquitectura?": "SELECT s.* FROM subjects s JOIN degree d ON s.degree_id = d.id WHERE d.name LIKE '%Arquitectura%' AND s.subject_code LIKE '1%'",

    # --- RESPUESTAS MULTI-TABLA (destinos + titulaciones/asignaturas/estudiantes) ---
    "Soy Russell Ryan, estudiante de Arquitectura. ¿A qué universidades de Italia puedo ir de Erasmus?": "SELECT * FROM students WHERE name LIKE '%Russell Ryan%'; SELECT host_institution, destination_country, uma_degrees, lang_1_name, lang_1_level, student_vacancies FROM destinations WHERE destination_country LIKE '%Italia%' AND uma_degrees LIKE '%Arquitectura%'",
    "¿Cuántas asignaturas tiene el grado en Arquitectura y cuántos destinos hay en Italia para esa titulación?": "SELECT COUNT(*) FROM subjects s JOIN degree d ON s.degree_id = d.id WHERE d.name LIKE '%Arquitectura%'; SELECT COUNT(*) FROM destinations WHERE destination_country LIKE '%Italia%' AND uma_degrees LIKE '%Arquitectura%'",
    "¿Existe el estudiante Charles Williams? Si es así, dime qué destinos hay en Alemania para Ingeniería Informática.": "SELECT * FROM students WHERE name LIKE '%Charles Williams%'; SELECT host_institution, destination_country, lang_1_name, lang_1_level FROM destinations WHERE destination_country LIKE '%Alemania%' AND uma_degrees LIKE '%Informática%'",
    "¿Qué destinos Erasmus hay para Medicina en Chile y cuántas asignaturas de tercer curso tiene esa titulación?": "SELECT * FROM destinations WHERE destination_country LIKE '%Chile%' AND uma_faculties LIKE '%Medicina%' AND mobility_program LIKE '%ERASMUS%'; SELECT COUNT(*) FROM subjects s JOIN degree d ON s.degree_id = d.id WHERE d.name LIKE '%Medicina%' AND s.subject_code LIKE '3%'",
    "¿Qué titulaciones de la UMA tienen convenios con universidades de Corea del Sur?": "SELECT DISTINCT uma_degrees FROM destinations WHERE destination_country LIKE '%Corea del Sur%'",
    "Soy Stephanie Smith, estudio Enfermería. ¿Qué nivel de inglés necesito para ir a Finlandia?": "SELECT * FROM students WHERE name LIKE '%Stephanie Smith%'; SELECT host_institution, lang_1_name, lang_1_level FROM destinations WHERE destination_country LIKE '%Finlandia%' AND uma_degrees LIKE '%Enfermería%' AND lang_1_name LIKE '%Inglés%'",
    "¿Cuántas asignaturas optativas tiene Derecho y qué destinos hay en Francia para esa titulación?": "SELECT COUNT(*) FROM subjects s JOIN degree d ON s.degree_id = d.id WHERE d.name LIKE '%Derecho%' AND (s.subject_code LIKE '8%' OR s.subject_code LIKE '9%'); SELECT host_institution, destination_country, lang_1_name, lang_1_level FROM destinations WHERE destination_country LIKE '%Francia%' AND uma_degrees LIKE '%Derecho%'",
    "¿Cuántos estudiantes hay matriculados y cuántos destinos Erasmus+ KA131 tiene la UMA?": "SELECT COUNT(*) FROM students; SELECT COUNT(*) FROM destinations WHERE mobility_program LIKE '%ERASMUS+ KA131%'",
    "Busca al estudiante Andrew Schwartz. Si estudiara Arquitectura, ¿podría ir a la Sapienza University of Rome?": "SELECT * FROM students WHERE name LIKE '%Andrew Schwartz%'; SELECT * FROM destinations WHERE host_institution LIKE '%Sapienza%' AND uma_degrees LIKE '%Arquitectura%'",
    "¿Qué asignaturas de primer curso tiene Ingeniería Informática y qué destinos hay sin requisito de idioma para esa titulación?": "SELECT s.name, s.subject_code FROM subjects s JOIN degree d ON s.degree_id = d.id WHERE d.name LIKE '%Ingeniería Informática%' AND s.subject_code LIKE '1%'; SELECT host_institution, destination_country FROM destinations WHERE uma_degrees LIKE '%Informática%' AND lang_1_name IS NULL",

    # --- RESPUESTAS EXTRACOMPLEJAS ---
    # Con errores ortográficos/gramaticales (el SQL debe ser correcto aunque la pregunta tenga errores)
    "que universidades hay en belgica para erasmus?": "SELECT host_institution FROM destinations WHERE destination_country LIKE '%Bélgica%' AND mobility_program LIKE '%ERASMUS%'",
    "¿Hay convenios con Finlandia o Noruega para ingenieria informatica?": "SELECT * FROM destinations WHERE (destination_country LIKE '%Finlandia%' OR destination_country LIKE '%Noruega%') AND uma_degrees LIKE '%Ingeniería Informática%'",
    "oye, donde puedo ir si hago derecho y quiero ir a sitios que no pidan mucho idioma?": "SELECT host_institution, destination_country FROM destinations WHERE uma_faculties LIKE '%Derecho%' AND (lang_1_name IS NULL OR lang_1_level = 'B1' OR lang_2_level = 'B1')",
    "QUIERO IR A ALEMANIA con nivel b1 de aleman, hay plazas?": "SELECT * FROM destinations WHERE destination_country LIKE '%Alemania%' AND ((lang_1_name LIKE '%Alemán%' AND lang_1_level = 'B1') OR (lang_2_name LIKE '%Alemán%' AND lang_2_level = 'B1')) AND student_vacancies NOT LIKE '%Plazas: 0%'",
    "q unis hay en italia pa medicina?": "SELECT host_institution FROM destinations WHERE destination_country LIKE '%Italia%' AND uma_faculties LIKE '%Medicina%'",
    "plazas italia ciencias inglés B2 hay?": "SELECT * FROM destinations WHERE destination_country LIKE '%Italia%' AND uma_faculties LIKE '%Ciencias%' AND ((lang_1_name LIKE '%Inglés%' AND lang_1_level = 'B2') OR (lang_2_name LIKE '%Inglés%' AND lang_2_level = 'B2')) AND student_vacancies NOT LIKE '%Plazas: 0%'",
    "convenios en paises nordicos sin requisito de idioma para filosofia y letras?": "SELECT * FROM destinations WHERE destination_country IN ('Dinamarca', 'Finlandia', 'Islandia', 'Noruega', 'Suecia') AND lang_1_name IS NULL AND uma_faculties LIKE '%Filosofía y Letras%'",

    # Con criterios adicionales (3-4 criterios)
    "¿Hay convenios en Francia para Económicas que pidan francés B2 y tengan plazas en el primer cuatrimestre?": "SELECT * FROM destinations WHERE destination_country LIKE '%Francia%' AND uma_faculties LIKE '%Económicas%' AND ((lang_1_name LIKE '%Francés%' AND lang_1_level = 'B2') OR (lang_2_name LIKE '%Francés%' AND lang_2_level = 'B2')) AND student_vacancies LIKE '%1er CUATRIMESTRE%' AND student_vacancies NOT LIKE '%Plazas: 0%'",
    "¿Qué universidades de Europa del Este tienen programa Erasmus para Derecho con inglés B1?": "SELECT host_institution, destination_country FROM destinations WHERE destination_country IN ('Bulgaria', 'Croacia', 'Eslovaquia', 'Eslovenia', 'Estonia', 'Hungría', 'Letonia', 'Lituania', 'Polonia', 'República Checa', 'Rumanía', 'Serbia', 'Ucrania') AND mobility_program LIKE '%ERASMUS%' AND uma_faculties LIKE '%Derecho%' AND ((lang_1_name LIKE '%Inglés%' AND lang_1_level = 'B1') OR (lang_2_name LIKE '%Inglés%' AND lang_2_level = 'B1'))",
    "¿Hay destinos en Alemania para estudiantes de Ciencias o Ingeniería que requieran alemán?": "SELECT * FROM destinations WHERE destination_country LIKE '%Alemania%' AND (uma_faculties LIKE '%Ciencias%' OR uma_faculties LIKE '%Ingeniería%') AND (lang_1_name LIKE '%Alemán%' OR lang_2_name LIKE '%Alemán%')",
    "¿Cuántas plazas Erasmus hay en países nórdicos para el segundo cuatrimestre?": "SELECT COUNT(*) FROM destinations WHERE destination_country IN ('Dinamarca', 'Finlandia', 'Islandia', 'Noruega', 'Suecia') AND mobility_program LIKE '%ERASMUS%' AND student_vacancies LIKE '%2º CUATRIMESTRE%' AND student_vacancies NOT LIKE '%Plazas: 0%'",
    "Universidades en Portugal para Turismo con portugués B1 y plazas disponibles": "SELECT host_institution FROM destinations WHERE destination_country LIKE '%Portugal%' AND uma_faculties LIKE '%Turismo%' AND ((lang_1_name LIKE '%Portugués%' AND lang_1_level = 'B1') OR (lang_2_name LIKE '%Portugués%' AND lang_2_level = 'B1')) AND student_vacancies NOT LIKE '%Plazas: 0%'",
    "¿Hay convenios ISEP en Latinoamérica para Medicina sin requisito de idioma?": "SELECT * FROM destinations WHERE mobility_program LIKE '%ISEP%' AND destination_country IN ('Argentina', 'Bolivia', 'Brasil', 'Chile', 'Colombia', 'Costa Rica', 'Ecuador', 'Honduras', 'México', 'Panamá', 'Paraguay', 'Perú', 'Puerto Rico', 'República Dominicana', 'Uruguay', 'Venezuela') AND uma_faculties LIKE '%Medicina%' AND lang_1_name IS NULL",
    "¿Qué opciones hay en Alemania, Austria o Suiza para Filosofía con alemán B2?": "SELECT * FROM destinations WHERE destination_country IN ('Alemania', 'Austria', 'Suiza') AND uma_faculties LIKE '%Filosofía%' AND ((lang_1_name LIKE '%Alemán%' AND lang_1_level = 'B2') OR (lang_2_name LIKE '%Alemán%' AND lang_2_level = 'B2'))",

    # Con regiones o grupos de países
    "¿Qué convenios hay con los países escandinavos para cualquier facultad?": "SELECT * FROM destinations WHERE destination_country IN ('Dinamarca', 'Finlandia', 'Islandia', 'Noruega', 'Suecia')",
    "¿Hay destinos en Europa del Este que no requieran idioma?": "SELECT * FROM destinations WHERE destination_country IN ('Bulgaria', 'Croacia', 'Eslovaquia', 'Eslovenia', 'Estonia', 'Hungría', 'Letonia', 'Lituania', 'Polonia', 'República Checa', 'Rumanía', 'Serbia', 'Ucrania') AND lang_1_name IS NULL",
    "¿Qué universidades hay en países de habla inglesa con plazas disponibles?": "SELECT host_institution, destination_country FROM destinations WHERE destination_country IN ('Irlanda', 'Reino Unido', 'Estados Unidos', 'Canadá', 'Australia') AND student_vacancies NOT LIKE '%Plazas: 0%'",
    "¿Hay convenios fuera de la Unión Europea para Ingeniería?": "SELECT * FROM destinations WHERE destination_country NOT IN ('Alemania', 'Austria', 'Bélgica', 'Bulgaria', 'Croacia', 'Dinamarca', 'Eslovaquia', 'Eslovenia', 'España', 'Estonia', 'Finlandia', 'Francia', 'Grecia', 'Hungría', 'Irlanda', 'Italia', 'Letonia', 'Lituania', 'Luxemburgo', 'Malta', 'Países Bajos', 'Polonia', 'Portugal', 'República Checa', 'República de Chipre', 'Rumanía', 'Suecia') AND uma_faculties LIKE '%Ingeniería%'",
    "Destinos en países mediterráneos con Erasmus+ para Turismo": "SELECT * FROM destinations WHERE destination_country IN ('España', 'Francia', 'Italia', 'Grecia', 'Croacia', 'Eslovenia', 'Malta', 'República de Chipre', 'Turquía', 'Marruecos', 'Túnez', 'Argelia', 'Egipto') AND mobility_program LIKE '%ERASMUS%' AND uma_faculties LIKE '%Turismo%'",
    "¿Qué opciones de movilidad hay en países de habla alemana para Económicas?": "SELECT * FROM destinations WHERE destination_country IN ('Alemania', 'Austria', 'Suiza') AND uma_faculties LIKE '%Económicas%'",
    "¿Hay plazas en el Benelux para estudiantes de Derecho con inglés o francés?": "SELECT * FROM destinations WHERE destination_country IN ('Bélgica', 'Países Bajos', 'Luxemburgo') AND uma_faculties LIKE '%Derecho%' AND (lang_1_name LIKE '%Inglés%' OR lang_2_name LIKE '%Inglés%' OR lang_1_name LIKE '%Francés%' OR lang_2_name LIKE '%Francés%') AND student_vacancies NOT LIKE '%Plazas: 0%'",

    "¿Qué destinos hay disponibles en Italia para grado de enfermería que no requieran título de idioma?": "SELECT * FROM destinations WHERE destination_country LIKE '%Italia%' AND uma_degrees LIKE '%Enfermería%' AND lang_1_name IS NULL",
    "¿Qué nivel de idioma se necesita para estudiar arquitectura en la universidad de La Sapienza?": "SELECT lang_1_name, lang_1_level, lang_2_name, lang_2_level FROM destinations WHERE host_institution LIKE '%La Sapienza%' AND uma_degrees LIKE '%Arquitectura%'",
    "¿Hace falta una nota media mínima para poder estudiar en la universidad de Berlín?": "SELECT host_institution, minimum_gpa FROM destinations WHERE host_institution LIKE '%Berlín%' OR host_institution LIKE '%Berlin%'",
    "¿Hay convenios en Japón que requieran coreano B2?": "SELECT * FROM destinations WHERE destination_country LIKE '%Japón%' AND ((lang_1_name LIKE '%Coreano%' AND lang_1_level = 'B2') OR (lang_2_name LIKE '%Coreano%' AND lang_2_level = 'B2'))",
    "¿Por qué no hay plazas con alemán B1 en Corea del Sur?": "SELECT * FROM destinations WHERE destination_country LIKE '%Corea del Sur%' AND ((lang_1_name LIKE '%Alemán%' AND lang_1_level = 'B1') OR (lang_2_name LIKE '%Alemán%' AND lang_2_level = 'B1')) AND student_vacancies NOT LIKE '%Plazas: 0%'",

    # --- RESPUESTAS EXTRACOMPLEJAS - ESTUDIANTES/ASIGNATURAS ---
    "busca a un estudiante que se llame Smith": "SELECT * FROM students WHERE name LIKE '%Smith%'",
    "q asignaturas tiene informatica de segundo?": "SELECT s.* FROM subjects s JOIN degree d ON s.degree_id = d.id WHERE d.name LIKE '%Informática%' AND s.subject_code LIKE '2%'",
    "cuantas optativas tiene el grado de biologia?": "SELECT COUNT(*) FROM subjects s JOIN degree d ON s.degree_id = d.id WHERE d.name LIKE '%Biología%' AND (s.subject_code LIKE '8%' OR s.subject_code LIKE '9%')",
    "How many students are enrolled?": "SELECT COUNT(*) FROM students",
    "¿Qué destinos Erasmus hay para estudiantes de Administración y Dirección de Empresas?": "SELECT * FROM destinations WHERE mobility_program LIKE '%ERASMUS%' AND uma_degrees LIKE '%Administración y Dirección de Empresas%'",

    # --- RESPUESTAS EXTRACOMPLEJAS - MULTI-TABLA ---
    "oye busca a Brady Brown, estudia arquitectura en la UMA y quiere irse de erasmus a italia, que opciones tiene?": "SELECT * FROM students WHERE name LIKE '%Brady Brown%'; SELECT host_institution, destination_country FROM destinations WHERE destination_country LIKE '%Italia%' AND uma_degrees LIKE '%Arquitectura%' AND mobility_program LIKE '%ERASMUS%'",
    "cuantas asignaturas tiene medicina y cuantos destinos hay en chile pa esa carrera?": "SELECT COUNT(*) FROM subjects s JOIN degree d ON s.degree_id = d.id WHERE d.name LIKE '%Medicina%'; SELECT COUNT(*) FROM destinations WHERE destination_country LIKE '%Chile%' AND uma_faculties LIKE '%Medicina%'",
    "Find student Michele Graham and show me destinations in Korea for Architecture": "SELECT * FROM students WHERE name LIKE '%Michele Graham%'; SELECT host_institution, destination_country FROM destinations WHERE destination_country LIKE '%Corea%' AND uma_degrees LIKE '%Arquitectura%'",
    "q destinos hay en alemania pa informatica y cuantas asignaturas optativas tiene?": "SELECT host_institution FROM destinations WHERE destination_country LIKE '%Alemania%' AND uma_degrees LIKE '%Informática%'; SELECT COUNT(*) FROM subjects s JOIN degree d ON s.degree_id = d.id WHERE d.name LIKE '%Informática%' AND (s.subject_code LIKE '8%' OR s.subject_code LIKE '9%')",
    "necesito nota media pa ir a la universidad de filipinas si estudio arquitectura?": "SELECT host_institution, min_gpa_requirement FROM destinations WHERE destination_country LIKE '%Filipinas%' AND uma_degrees LIKE '%Arquitectura%'",
}


# ============================================================================
# ESCENARIOS DE CONVERSACIÓN (refinamiento, ampliación, vuelta atrás)
# ============================================================================

ESCENARIOS_CONVERSACION = [
    # --- Escenario 1: Refinamiento por país + nivel de idioma ---
    {
        "nombre": "Refinamiento: País → Nivel idioma",
        "descripcion": "Buscar en Alemania, luego filtrar por nivel B1",
        "pasos": [
            {
                "pregunta": "¿Hay convenios en Alemania que requieran inglés?",
                "tipo": "inicial",
                "validar": {
                    "sql_contiene": ["destination_country", "Alemania", "INGLÉS"],
                    "resultados_min": 50
                }
            },
            {
                "pregunta": "Solo los de nivel B1",
                "tipo": "refinamiento",
                "validar": {
                    "sql_contiene": ["Alemania", "INGLÉS", "B1"],
                    "resultados_menor_que_anterior": True
                }
            }
        ]
    },

    # --- Escenario 2: Refinamiento por nivel + cambio de nivel ---
    {
        "nombre": "Refinamiento: Cambio de nivel B1 → B2",
        "descripcion": "Filtrar por B1, luego cambiar a B2 (debe sustituir, no añadir)",
        "pasos": [
            {
                "pregunta": "Convenios con inglés B1 en Alemania",
                "tipo": "inicial",
                "validar": {
                    "sql_contiene": ["Alemania", "INGLÉS", "B1"]
                }
            },
            {
                "pregunta": "Muestra los de nivel B2",
                "tipo": "refinamiento",
                "validar": {
                    "sql_contiene": ["Alemania", "INGLÉS", "B2"],
                    "sql_no_contiene": ["B1"]  # B1 debe ser sustituido por B2
                }
            }
        ]
    },

    # --- Escenario 3: Refinamiento por región ---
    {
        "nombre": "Refinamiento: Cambio de país a región",
        "descripcion": "Filtrar por Alemania, luego cambiar a Asia (debe sustituir país)",
        "pasos": [
            {
                "pregunta": "Convenios con inglés B1 en Alemania",
                "tipo": "inicial",
                "validar": {
                    "sql_contiene": ["Alemania", "INGLÉS", "B1"]
                }
            },
            {
                "pregunta": "Muéstrame los de Asia",
                "tipo": "refinamiento",
                "validar": {
                    "sql_contiene": ["INGLÉS", "B1"],
                    "sql_no_contiene": ["Alemania"],  # Alemania debe ser sustituida
                    "sql_contiene_alguno": ["Asia", "Japón", "Corea", "IN ("]  # Región expandida
                }
            }
        ]
    },

    # --- Escenario 4: Refinamiento por universidad específica ---
    {
        "nombre": "Refinamiento: Añadir universidad",
        "descripcion": "Filtrar por país, luego añadir universidad específica",
        "pasos": [
            {
                "pregunta": "¿Hay convenios en Alemania que requieran inglés?",
                "tipo": "inicial",
                "validar": {
                    "sql_contiene": ["Alemania", "INGLÉS"]
                }
            },
            {
                "pregunta": "Los de TECHNISCHE UNIVERSITÄT ILMENAU",
                "tipo": "refinamiento",
                "validar": {
                    "sql_contiene": ["Alemania", "INGLÉS", "host_institution", "TECHNISCHE"]
                }
            }
        ]
    },

    # --- Escenario 5: Refinamiento por cuatrimestre ---
    {
        "nombre": "Refinamiento: Añadir cuatrimestre",
        "descripcion": "Filtrar por país e idioma, luego añadir cuatrimestre",
        "pasos": [
            {
                "pregunta": "Convenios con inglés B1 en Alemania",
                "tipo": "inicial",
                "validar": {
                    "sql_contiene": ["Alemania", "INGLÉS", "B1"]
                }
            },
            {
                "pregunta": "Solo los del primer cuatrimestre",
                "tipo": "refinamiento",
                "validar": {
                    "sql_contiene": ["Alemania", "INGLÉS", "B1", "1er CUATRIMESTRE"]
                }
            }
        ]
    },

    # --- Escenario 6: Ampliar detalles de convenio ---
    {
        "nombre": "Ampliación: Ver detalles de convenio",
        "descripcion": "Hacer consulta y ampliar detalles del primer resultado",
        "pasos": [
            {
                "pregunta": "¿Qué acuerdos hay con The Hague University of Applied Sciences?",
                "tipo": "inicial",
                "validar": {
                    "sql_contiene": ["The Hague"],
                    "resultados_min": 1
                }
            },
            {
                "pregunta": "Amplía el 1",
                "tipo": "ampliar",
                "validar": {
                    "respuesta_contiene": ["Detalles del acuerdo", "Vigencia", "Plazas"]
                }
            }
        ]
    },

    # --- Escenario 7: Paginación ---
    {
        "nombre": "Paginación: Ver más resultados",
        "descripcion": "Consulta con muchos resultados, pedir ver más",
        "pasos": [
            {
                "pregunta": "¿Qué destinos hay en Europa?",
                "tipo": "inicial",
                "validar": {
                    "resultados_min": 100
                }
            },
            {
                "pregunta": "Muéstrame más",
                "tipo": "paginacion",
                "validar": {
                    "respuesta_contiene": ["Mostrando resultados", "de"]
                }
            }
        ]
    },

    # --- Escenario 8: Secuencia completa (refinamiento múltiple) ---
    {
        "nombre": "Secuencia completa: Múltiples refinamientos",
        "descripcion": "Refinar varias veces añadiendo criterios",
        "pasos": [
            {
                "pregunta": "Convenios en Alemania",
                "tipo": "inicial",
                "validar": {
                    "sql_contiene": ["Alemania"]
                }
            },
            {
                "pregunta": "Los que requieran inglés",
                "tipo": "refinamiento",
                "validar": {
                    "sql_contiene": ["Alemania", "INGLÉS"]
                }
            },
            {
                "pregunta": "Solo nivel B1",
                "tipo": "refinamiento",
                "validar": {
                    "sql_contiene": ["Alemania", "INGLÉS", "B1"]
                }
            }
        ]
    },

    # --- Escenario 9: "Solo los que..." con plazas disponibles ---
    {
        "nombre": "Filtro: Solo los que tengan plazas",
        "descripcion": "Buscar en un país y filtrar solo los que tengan plazas disponibles",
        "pasos": [
            {
                "pregunta": "¿Qué convenios hay en Italia?",
                "tipo": "inicial",
                "validar": {
                    "sql_contiene": ["Italia"],
                    "resultados_min": 10
                }
            },
            {
                "pregunta": "Solo los que tengan plazas disponibles",
                "tipo": "refinamiento",
                "validar": {
                    "sql_contiene": ["Italia", "student_vacancies"],
                    "sql_contiene_alguno": ["NOT LIKE '%Plazas: 0%'", "Plazas"],
                    "resultados_menor_que_anterior": True
                }
            }
        ]
    },

    # --- Escenario 10: "Muestra también..." ampliando países ---
    {
        "nombre": "Ampliación: Muestra también otro país",
        "descripcion": "Buscar en un país y ampliar añadiendo otro país",
        "pasos": [
            {
                "pregunta": "Convenios con inglés B1 en Alemania",
                "tipo": "inicial",
                "validar": {
                    "sql_contiene": ["Alemania", "INGLÉS", "B1"]
                }
            },
            {
                "pregunta": "Muestra también los de Francia",
                "tipo": "ampliacion",
                "validar": {
                    "sql_contiene": ["INGLÉS", "B1"],
                    "sql_contiene_alguno": ["Francia", "OR"],
                    "sql_no_contiene": []  # Alemania debe seguir presente
                }
            }
        ]
    },

    # --- Escenario 11: "Solo los de..." facultad específica ---
    {
        "nombre": "Filtro: Solo los de una facultad",
        "descripcion": "Buscar en un país y filtrar por facultad",
        "pasos": [
            {
                "pregunta": "¿Hay convenios en Alemania?",
                "tipo": "inicial",
                "validar": {
                    "sql_contiene": ["Alemania"],
                    "resultados_min": 50
                }
            },
            {
                "pregunta": "Solo los de la Facultad de Derecho",
                "tipo": "refinamiento",
                "validar": {
                    "sql_contiene": ["Alemania", "uma_faculties", "Derecho"],
                    "resultados_menor_que_anterior": True
                }
            }
        ]
    },

    # --- Escenario 12: "Muestra también..." añadiendo idioma ---
    {
        "nombre": "Ampliación: Muestra también otro idioma",
        "descripcion": "Buscar con un idioma y ampliar con otro",
        "pasos": [
            {
                "pregunta": "Convenios en Alemania que pidan inglés",
                "tipo": "inicial",
                "validar": {
                    "sql_contiene": ["Alemania", "INGLÉS"]
                }
            },
            {
                "pregunta": "Muestra también los que pidan alemán",
                "tipo": "ampliacion",
                "validar": {
                    "sql_contiene": ["Alemania"],
                    "sql_contiene_alguno": ["ALEMÁN", "OR"],
                }
            }
        ]
    },

    # --- Escenario 13: "Solo los del primer cuatrimestre" ---
    {
        "nombre": "Filtro: Solo los del primer cuatrimestre",
        "descripcion": "Buscar convenios y filtrar por cuatrimestre específico",
        "pasos": [
            {
                "pregunta": "¿Qué convenios hay en Francia para Economía?",
                "tipo": "inicial",
                "validar": {
                    "sql_contiene": ["Francia"],
                    "sql_contiene_alguno": ["Económicas", "Economía", "uma_faculties"]
                }
            },
            {
                "pregunta": "Solo los del primer cuatrimestre",
                "tipo": "refinamiento",
                "validar": {
                    "sql_contiene": ["Francia", "1er CUATRIMESTRE"],
                    "resultados_menor_que_anterior": True
                }
            }
        ]
    },

    # --- Escenario 14: "Solo los que no requieran idioma" ---
    {
        "nombre": "Filtro: Solo los que no requieran idioma",
        "descripcion": "Buscar en Europa y filtrar sin requisito de idioma",
        "pasos": [
            {
                "pregunta": "¿Qué destinos hay en países nórdicos?",
                "tipo": "inicial",
                "validar": {
                    "sql_contiene_alguno": ["Finlandia", "Noruega", "Suecia", "Dinamarca", "IN ("]
                }
            },
            {
                "pregunta": "Solo los que no requieran acreditación de idioma",
                "tipo": "refinamiento",
                "validar": {
                    "sql_contiene": ["lang_1_name"],
                    "sql_contiene_alguno": ["IS NULL", "NULL"],
                    "resultados_menor_que_anterior": True
                }
            }
        ]
    },

    # --- Escenario 15: "Muestra también..." añadiendo programa ---
    {
        "nombre": "Ampliación: Muestra también otro programa",
        "descripcion": "Buscar con Erasmus y ampliar con ISEP",
        "pasos": [
            {
                "pregunta": "Convenios Erasmus en Italia",
                "tipo": "inicial",
                "validar": {
                    "sql_contiene": ["Italia", "ERASMUS"]
                }
            },
            {
                "pregunta": "Muestra también los de ISEP",
                "tipo": "ampliacion",
                "validar": {
                    "sql_contiene": ["Italia"],
                    "sql_contiene_alguno": ["ISEP", "OR"],
                }
            }
        ]
    },

    # --- Escenario 16: Combinación "solo los que" + "muestra también" ---
    {
        "nombre": "Combinación: Filtrar y luego ampliar",
        "descripcion": "Filtrar por criterio y luego ampliar con más opciones",
        "pasos": [
            {
                "pregunta": "¿Qué convenios hay en Alemania?",
                "tipo": "inicial",
                "validar": {
                    "sql_contiene": ["Alemania"],
                    "guardar_resultados": True
                }
            },
            {
                "pregunta": "Solo los que pidan inglés B1",
                "tipo": "refinamiento",
                "validar": {
                    "sql_contiene": ["Alemania", "INGLÉS", "B1"],
                    "resultados_menor_que_anterior": True
                }
            },
            {
                "pregunta": "Muestra también los de nivel B2",
                "tipo": "ampliacion",
                "validar": {
                    "sql_contiene": ["Alemania", "INGLÉS"],
                    "sql_contiene_alguno": ["B2", "OR"],
                }
            }
        ]
    },

    # --- Escenario 17: "Solo los de..." con múltiples criterios ---
    {
        "nombre": "Filtro múltiple: Solo los que cumplan varios criterios",
        "descripcion": "Añadir múltiples filtros secuencialmente",
        "pasos": [
            {
                "pregunta": "Convenios en Italia",
                "tipo": "inicial",
                "validar": {
                    "sql_contiene": ["Italia"],
                    "guardar_resultados": True
                }
            },
            {
                "pregunta": "Solo los de Medicina",
                "tipo": "refinamiento",
                "validar": {
                    "sql_contiene": ["Italia", "Medicina"],
                    "resultados_menor_que_anterior": True
                }
            },
            {
                "pregunta": "Y solo los que tengan plazas",
                "tipo": "refinamiento",
                "validar": {
                    "sql_contiene": ["Italia", "Medicina", "student_vacancies"],
                }
            }
        ]
    },
]

# Escenarios rápidos para pruebas
ESCENARIOS_QUICK = [
    ESCENARIOS_CONVERSACION[0],  # Refinamiento básico
    ESCENARIOS_CONVERSACION[5],  # Ampliar detalles
    ESCENARIOS_CONVERSACION[6],  # Paginación
]


def validate_step(step: dict, agent: Agent, response: str, prev_results: int = None, saved_results: int = None) -> dict:
    """
    Valida un paso de un escenario de conversación.

    Args:
        step: El paso a validar con sus criterios
        agent: Instancia del agente (para acceder al SQL generado)
        response: Respuesta del agente
        prev_results: Número de resultados del paso anterior (para comparaciones)
        saved_results: Número de resultados guardados (para restauración)

    Returns:
        dict con resultado de validación {passed: bool, errors: list}
    """
    validar = step.get("validar", {})
    errors = []

    sql_query = agent.last_sql_query or ""
    num_results = len(agent.last_results) if agent.last_results else 0

    # Validar sql_contiene
    if "sql_contiene" in validar:
        for term in validar["sql_contiene"]:
            if term.upper() not in sql_query.upper():
                errors.append(f"SQL no contiene '{term}'")

    # Validar sql_no_contiene
    if "sql_no_contiene" in validar:
        for term in validar["sql_no_contiene"]:
            if term.upper() in sql_query.upper():
                errors.append(f"SQL contiene '{term}' (no debería)")

    # Validar sql_contiene_alguno
    if "sql_contiene_alguno" in validar:
        found = False
        for term in validar["sql_contiene_alguno"]:
            if term.upper() in sql_query.upper():
                found = True
                break
        if not found:
            errors.append(f"SQL no contiene ninguno de: {validar['sql_contiene_alguno']}")

    # Validar resultados_min
    if "resultados_min" in validar:
        if num_results < validar["resultados_min"]:
            errors.append(f"Resultados ({num_results}) menor que mínimo ({validar['resultados_min']})")

    # Validar resultados_menor_que_anterior
    if validar.get("resultados_menor_que_anterior") and prev_results is not None:
        if num_results >= prev_results:
            errors.append(f"Resultados ({num_results}) no menor que anterior ({prev_results})")

    # Validar restaura_resultados_guardados
    if validar.get("restaura_resultados_guardados") and saved_results is not None:
        if num_results != saved_results:
            errors.append(f"Resultados ({num_results}) no coinciden con guardados ({saved_results})")

    # Validar respuesta_contiene
    if "respuesta_contiene" in validar:
        for term in validar["respuesta_contiene"]:
            if term.lower() not in response.lower():
                errors.append(f"Respuesta no contiene '{term}'")

    return {
        "passed": len(errors) == 0,
        "errors": errors,
        "sql": sql_query,
        "num_results": num_results
    }


def run_scenario_benchmark(scenarios: list, output_prefix: str = "scenarios") -> dict:
    """
    Ejecuta el benchmark de escenarios de conversación.

    Args:
        scenarios: Lista de escenarios a ejecutar
        output_prefix: Prefijo para el archivo de salida

    Returns:
        dict con resultados del benchmark de escenarios
    """
    print("=" * 70)
    print("BENCHMARK PISHA4 - Escenarios de Conversación")
    print("=" * 70)
    print(f"Escenarios a ejecutar: {len(scenarios)}")
    print(f"Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    print()

    results = {
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "num_scenarios": len(scenarios),
            "type": "conversation_scenarios"
        },
        "scenarios": [],
        "summary": {
            "total_scenarios": len(scenarios),
            "passed_scenarios": 0,
            "failed_scenarios": 0,
            "total_steps": 0,
            "passed_steps": 0,
            "failed_steps": 0,
        }
    }

    for i, scenario in enumerate(scenarios, 1):
        print(f"\n{'='*70}")
        print(f"ESCENARIO {i}/{len(scenarios)}: {scenario['nombre']}")
        print(f"  {scenario['descripcion']}")
        print("-" * 70)

        # Crear nuevo agente para cada escenario (sesión limpia)
        agent = Agent()

        scenario_result = {
            "nombre": scenario["nombre"],
            "descripcion": scenario["descripcion"],
            "pasos": [],
            "passed": True
        }

        prev_results = None
        saved_results = None

        for j, paso in enumerate(scenario["pasos"], 1):
            pregunta = paso["pregunta"]
            tipo = paso["tipo"]

            print(f"\n  [{j}] ({tipo}) {pregunta}")

            try:
                # Ejecutar pregunta
                response = agent.chat(pregunta)

                # Guardar resultados si se solicita
                if paso.get("validar", {}).get("guardar_resultados"):
                    saved_results = len(agent.last_results) if agent.last_results else 0
                    print(f"      📌 Guardando {saved_results} resultados para referencia")

                # Validar paso
                validation = validate_step(paso, agent, response, prev_results, saved_results)

                step_result = {
                    "pregunta": pregunta,
                    "tipo": tipo,
                    "sql": validation["sql"],
                    "num_results": validation["num_results"],
                    "passed": validation["passed"],
                    "errors": validation["errors"]
                }
                scenario_result["pasos"].append(step_result)
                results["summary"]["total_steps"] += 1

                if validation["passed"]:
                    print(f"      ✅ OK | Resultados: {validation['num_results']}")
                    if validation["sql"]:
                        print(f"      SQL: {validation['sql']}")
                    results["summary"]["passed_steps"] += 1
                else:
                    print(f"      ❌ FALLÓ")
                    for error in validation["errors"]:
                        print(f"         - {error}")
                    if validation["sql"]:
                        print(f"      SQL: {validation['sql']}")
                    scenario_result["passed"] = False
                    results["summary"]["failed_steps"] += 1

                # Actualizar prev_results para siguiente paso
                prev_results = validation["num_results"]

            except Exception as e:
                print(f"      ❌ EXCEPCIÓN: {str(e)}")
                scenario_result["pasos"].append({
                    "pregunta": pregunta,
                    "tipo": tipo,
                    "passed": False,
                    "errors": [f"Excepción: {str(e)}"]
                })
                scenario_result["passed"] = False
                results["summary"]["total_steps"] += 1
                results["summary"]["failed_steps"] += 1

        # Resumen del escenario
        results["scenarios"].append(scenario_result)
        if scenario_result["passed"]:
            print(f"\n  ✅ ESCENARIO PASÓ")
            results["summary"]["passed_scenarios"] += 1
        else:
            print(f"\n  ❌ ESCENARIO FALLÓ")
            results["summary"]["failed_scenarios"] += 1

    # Resumen final
    print("\n" + "=" * 70)
    print("RESUMEN DEL BENCHMARK DE ESCENARIOS")
    print("=" * 70)
    print(f"Escenarios ejecutados: {results['summary']['total_scenarios']}")
    print(f"  ✅ Pasaron: {results['summary']['passed_scenarios']}")
    print(f"  ❌ Fallaron: {results['summary']['failed_scenarios']}")
    print(f"Pasos ejecutados: {results['summary']['total_steps']}")
    print(f"  ✅ Pasaron: {results['summary']['passed_steps']}")
    print(f"  ❌ Fallaron: {results['summary']['failed_steps']}")
    print("=" * 70)

    # Guardar resultados
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"{output_prefix}_{timestamp}.json"
    output_path = os.path.join(os.path.dirname(__file__), "logs", output_file)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\nResultados guardados en: {output_path}")

    # Generar log legible
    log_file = f"{output_prefix}_{timestamp}.log"
    log_path = os.path.join(os.path.dirname(__file__), "logs", log_file)

    with open(log_path, "w", encoding="utf-8") as f:
        f.write("=" * 80 + "\n")
        f.write(f"BENCHMARK ESCENARIOS PISHA3 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 80 + "\n\n")

        f.write("RESUMEN\n")
        f.write("-" * 40 + "\n")
        f.write(f"Escenarios: {results['summary']['total_scenarios']} "
                f"(✅ {results['summary']['passed_scenarios']} / ❌ {results['summary']['failed_scenarios']})\n")
        f.write(f"Pasos: {results['summary']['total_steps']} "
                f"(✅ {results['summary']['passed_steps']} / ❌ {results['summary']['failed_steps']})\n\n")

        f.write("=" * 80 + "\n")
        f.write("DETALLE POR ESCENARIO\n")
        f.write("=" * 80 + "\n\n")

        for scenario in results["scenarios"]:
            status = "✅" if scenario["passed"] else "❌"
            f.write(f"{status} {scenario['nombre']}\n")
            f.write(f"   {scenario['descripcion']}\n\n")

            for paso in scenario["pasos"]:
                paso_status = "✅" if paso["passed"] else "❌"
                f.write(f"   {paso_status} [{paso['tipo']}] {paso['pregunta']}\n")
                if paso.get("sql"):
                    f.write(f"      SQL: {paso['sql']}\n")
                f.write(f"      Resultados: {paso.get('num_results', 'N/A')}\n")
                if paso.get("errors"):
                    for error in paso["errors"]:
                        f.write(f"      ❌ {error}\n")
                f.write("\n")
            f.write("-" * 80 + "\n\n")

    print(f"Log legible guardado en: {log_path}")

    return results


def run_benchmark(questions: list, output_prefix: str = "benchmark") -> dict:
    """
    Ejecuta el benchmark con las preguntas proporcionadas.

    Args:
        questions: Lista de preguntas a ejecutar
        output_prefix: Prefijo para el archivo de salida

    Returns:
        dict con resultados del benchmark
    """
    print("=" * 70)
    print("BENCHMARK PISHA4 - Prueba de Rendimiento")
    print("=" * 70)
    print(f"Preguntas a ejecutar: {len(questions)}")
    print(f"Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    print()

    # Inicializar agente
    print("Inicializando agente...")
    agent = Agent()
    print(f"Modelo SQL: {agent.sql_model}")
    print(f"Base de datos: {agent.db_path}")
    print()

    # Resultados del benchmark
    results = {
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "num_questions": len(questions),
            "num_warmup": 1,
            "num_benchmark": len(questions) - 1,
            "sql_model": agent.sql_model,
            "db_path": agent.db_path,
        },
        "questions": [],
        "summary": {
            "total_time": 0,
            "avg_time": 0,
            "successful": 0,
            "failed": 0,
            "sql_errors_count": 0,  # Número de sentencias con algún error SQL
            "sql_errors_total": 0,  # Número total de errores SQL
            "avg_time_text_to_sql": 0,
            "avg_time_execute": 0,
        }
    }

    total_time = 0
    total_text_to_sql = 0
    total_execute = 0

    # Listas para cálculos estadísticos (excluyendo warm-up)
    times_total = []
    times_text_to_sql = []
    times_execute = []

    # Métricas de warm-up (primera pregunta)
    warmup_metrics = {
        "total_time": 0,
        "time_text_to_sql": 0,
        "time_execute": 0,
    }

    # Ejecutar cada pregunta
    for i, question in enumerate(questions, 1):
        is_warmup = (i == 1)
        warmup_tag = " [WARM-UP]" if is_warmup else ""
        print(f"[{i}/{len(questions)}]{warmup_tag} {question[:60]}...")

        # Mostrar respuesta SQL de referencia si existe
        sql_referencia = RESPUESTAS_REFERENCIA.get(question, None)
        if sql_referencia:
            print(f"    Ref: {sql_referencia}")

        try:
            metrics = agent.chat_with_metrics(question)

            # Detectar si hubo error SQL (no success o error no vacío)
            has_sql_error = not metrics["success"] or metrics.get("error")
            if has_sql_error:
                results["summary"]["sql_errors_count"] += 1
                results["summary"]["sql_errors_total"] += 1

            # Guardar resultado
            question_result = {
                "id": i,
                "question": question,
                "is_warmup": is_warmup,
                "sql_query": metrics["sql_query"],
                "sql_referencia": sql_referencia,
                "success": metrics["success"],
                "has_sql_error": has_sql_error,
                "num_results": metrics["num_results"],
                "timings": metrics["timings"],
                "total_time": metrics["total_time"],
                "error": metrics["error"]
            }
            results["questions"].append(question_result)

            # Acumular tiempos (separando warm-up del resto)
            if is_warmup:
                warmup_metrics["total_time"] = metrics["total_time"]
                if "2_text_to_sql" in metrics["timings"]:
                    warmup_metrics["time_text_to_sql"] = metrics["timings"]["2_text_to_sql"]
                if "3_execute_sql" in metrics["timings"]:
                    warmup_metrics["time_execute"] = metrics["timings"]["3_execute_sql"]
            else:
                total_time += metrics["total_time"]
                times_total.append(metrics["total_time"])
                if "2_text_to_sql" in metrics["timings"]:
                    t2sql = metrics["timings"]["2_text_to_sql"]
                    total_text_to_sql += t2sql
                    times_text_to_sql.append(t2sql)
                if "3_execute_sql" in metrics["timings"]:
                    texec = metrics["timings"]["3_execute_sql"]
                    total_execute += texec
                    times_execute.append(texec)

            # Mostrar resultado
            status = "OK" if metrics["success"] else "ERROR"
            print(f"    -> {status} | {metrics['total_time']:.2f}s | "
                  f"SQL: {metrics['timings'].get('2_text_to_sql', 0):.2f}s | "
                  f"Exec: {metrics['timings'].get('3_execute_sql', 0):.4f}s | "
                  f"Resultados: {metrics['num_results']}")

            if metrics["success"]:
                results["summary"]["successful"] += 1
            else:
                results["summary"]["failed"] += 1
                if metrics["error"]:
                    print(f"    !! Error: {metrics['error'][:80]}")

        except Exception as e:
            print(f"    !! Excepción: {str(e)}")
            results["questions"].append({
                "id": i,
                "question": question,
                "sql_query": None,
                "success": False,
                "error": str(e),
                "timings": {},
                "total_time": 0
            })
            results["summary"]["failed"] += 1

        print()

    # Calcular resumen (n_rest = preguntas sin warm-up)
    n = len(questions)
    n_rest = n - 1 if n > 1 else 0

    # Tiempos totales (warm-up + resto)
    results["summary"]["total_time"] = round(warmup_metrics["total_time"] + total_time, 2)

    # Métricas del warm-up
    results["summary"]["warmup"] = {
        "total_time": round(warmup_metrics["total_time"], 2),
        "time_text_to_sql": round(warmup_metrics["time_text_to_sql"], 2),
        "time_execute": round(warmup_metrics["time_execute"], 4),
    }

    # Métricas del resto (excluyendo warm-up)
    results["summary"]["rest_total_time"] = round(total_time, 2)
    results["summary"]["avg_time"] = round(total_time / n_rest, 2) if n_rest > 0 else 0
    results["summary"]["avg_time_text_to_sql"] = round(total_text_to_sql / n_rest, 2) if n_rest > 0 else 0
    results["summary"]["avg_time_execute"] = round(total_execute / n_rest, 4) if n_rest > 0 else 0

    # Calcular desviación estándar y percentil 90
    def calc_stats(times_list):
        """Calcula std dev y p90 para una lista de tiempos."""
        if len(times_list) < 2:
            return 0, times_list[0] if times_list else 0
        std_dev = statistics.stdev(times_list)
        p90 = statistics.quantiles(times_list, n=10)[8] if len(times_list) >= 2 else times_list[-1]
        return round(std_dev, 3), round(p90, 3)

    std_total, p90_total = calc_stats(times_total)
    std_text_to_sql, p90_text_to_sql = calc_stats(times_text_to_sql)
    std_execute, p90_execute = calc_stats(times_execute)

    results["summary"]["std_time"] = std_total
    results["summary"]["p90_time"] = p90_total
    results["summary"]["std_time_text_to_sql"] = std_text_to_sql
    results["summary"]["p90_time_text_to_sql"] = p90_text_to_sql
    results["summary"]["std_time_execute"] = std_execute
    results["summary"]["p90_time_execute"] = p90_execute

    # Mostrar resumen
    print("=" * 70)
    print("RESUMEN DEL BENCHMARK")
    print("=" * 70)
    print(f"Preguntas ejecutadas: {n} (1 warm-up + {n_rest} benchmark)")
    print(f"Exitosas: {results['summary']['successful']}")
    print(f"Fallidas: {results['summary']['failed']}")
    print(f"Errores SQL: {results['summary']['sql_errors_count']} sentencias con error ({results['summary']['sql_errors_total']} errores totales)")
    print(f"Tiempo total: {results['summary']['total_time']:.2f}s")
    print()
    print("WARM-UP (primera pregunta):")
    print(f"  Total: {results['summary']['warmup']['total_time']:.2f}s | "
          f"Text-to-SQL: {results['summary']['warmup']['time_text_to_sql']:.2f}s | "
          f"Exec: {results['summary']['warmup']['time_execute']:.4f}s")
    print()
    print(f"BENCHMARK (preguntas {2}-{n}):")
    print(f"  Tiempo total: {results['summary']['rest_total_time']:.2f}s")
    print(f"  Tiempo por pregunta:")
    print(f"    Promedio: {results['summary']['avg_time']:.2f}s | Std Dev: {std_total:.3f}s | P90: {p90_total:.3f}s")
    print(f"  Text-to-SQL (LLM):")
    print(f"    Promedio: {results['summary']['avg_time_text_to_sql']:.2f}s | Std Dev: {std_text_to_sql:.3f}s | P90: {p90_text_to_sql:.3f}s")
    print(f"  Ejecución SQL:")
    print(f"    Promedio: {results['summary']['avg_time_execute']:.4f}s | Std Dev: {std_execute:.4f}s | P90: {p90_execute:.4f}s")
    print("=" * 70)

    # Guardar resultados en archivo JSON
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"{output_prefix}_{timestamp}.json"
    output_path = os.path.join(os.path.dirname(__file__), "logs", output_file)

    # Crear directorio logs si no existe
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\nResultados guardados en: {output_path}")

    # Generar también un log legible
    log_file = f"{output_prefix}_{timestamp}.log"
    log_path = os.path.join(os.path.dirname(__file__), "logs", log_file)

    with open(log_path, "w", encoding="utf-8") as f:
        f.write("=" * 80 + "\n")
        f.write(f"BENCHMARK PISHA4 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 80 + "\n\n")

        f.write(f"Modelo: {agent.sql_model}\n")
        f.write(f"Preguntas: {n} (1 warm-up + {n_rest} benchmark)\n")
        f.write(f"Exitosas: {results['summary']['successful']}\n")
        f.write(f"Fallidas: {results['summary']['failed']}\n")
        f.write(f"Errores SQL: {results['summary']['sql_errors_count']} sentencias con error ")
        f.write(f"({results['summary']['sql_errors_total']} errores totales)\n\n")

        f.write("-" * 80 + "\n")
        f.write("DETALLE POR PREGUNTA\n")
        f.write("-" * 80 + "\n\n")

        for q in results["questions"]:
            warmup_tag = " [WARM-UP]" if q.get('is_warmup') else ""
            f.write(f"[{q['id']}]{warmup_tag} {q['question']}\n")
            if q.get('sql_referencia'):
                f.write(f"    SQL Referencia: {q['sql_referencia']}\n")
            f.write(f"    SQL Generado:   {q['sql_query']}\n")
            f.write(f"    Status: {'OK' if q['success'] else 'ERROR'}\n")
            f.write(f"    Resultados: {q['num_results']}\n")
            f.write(f"    Tiempos:\n")
            for fase, tiempo in q.get("timings", {}).items():
                f.write(f"        {fase}: {tiempo}s\n")
            f.write(f"    Total: {q['total_time']}s\n")
            if q.get("error"):
                f.write(f"    Error: {q['error']}\n")
            f.write("\n")

        f.write("-" * 80 + "\n")
        f.write("RESUMEN\n")
        f.write("-" * 80 + "\n")
        f.write(f"Preguntas: {n} (1 warm-up + {n_rest} benchmark)\n")
        f.write(f"Tiempo total: {results['summary']['total_time']}s\n\n")
        f.write(f"Errores SQL:\n")
        f.write(f"  Sentencias con error: {results['summary']['sql_errors_count']}\n")
        f.write(f"  Total de errores: {results['summary']['sql_errors_total']}\n\n")

        f.write("WARM-UP (primera pregunta):\n")
        f.write(f"  Total: {results['summary']['warmup']['total_time']}s\n")
        f.write(f"  Text-to-SQL: {results['summary']['warmup']['time_text_to_sql']}s\n")
        f.write(f"  Ejecución SQL: {results['summary']['warmup']['time_execute']}s\n\n")

        f.write(f"BENCHMARK (preguntas 2-{n}):\n")
        f.write(f"  Tiempo total: {results['summary']['rest_total_time']}s\n\n")
        f.write(f"  Tiempo por pregunta:\n")
        f.write(f"    Promedio: {results['summary']['avg_time']}s\n")
        f.write(f"    Desv. Estándar: {results['summary']['std_time']}s\n")
        f.write(f"    Percentil 90: {results['summary']['p90_time']}s\n\n")
        f.write(f"  Text-to-SQL (LLM):\n")
        f.write(f"    Promedio: {results['summary']['avg_time_text_to_sql']}s\n")
        f.write(f"    Desv. Estándar: {results['summary']['std_time_text_to_sql']}s\n")
        f.write(f"    Percentil 90: {results['summary']['p90_time_text_to_sql']}s\n\n")
        f.write(f"  Ejecución SQL:\n")
        f.write(f"    Promedio: {results['summary']['avg_time_execute']}s\n")
        f.write(f"    Desv. Estándar: {results['summary']['std_time_execute']}s\n")
        f.write(f"    Percentil 90: {results['summary']['p90_time_execute']}s\n")

    print(f"Log legible guardado en: {log_path}")

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Benchmark de Pisha2 - Pruebas de rendimiento del agente Text-to-SQL",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  python benchmark.py -q           # Ejecutar todas las preguntas
  python benchmark.py -q 10        # Ejecutar solo 10 preguntas
  python benchmark.py -s           # Ejecutar todos los escenarios
  python benchmark.py -s 5         # Ejecutar solo 5 escenarios
  python benchmark.py --all        # Ejecutar todo (preguntas + escenarios)
  python benchmark.py -q -s        # Ejecutar todas las preguntas y escenarios
  python benchmark.py -i           # Ejecutar solo preguntas de idiomas
"""
    )
    parser.add_argument(
        "-q", "--questions",
        type=int,
        nargs="?",
        const=-1,
        default=None,
        metavar="N",
        help="Ejecutar preguntas (sin N = todas, con N = solo N preguntas)"
    )
    parser.add_argument(
        "-s", "--scenarios",
        type=int,
        nargs="?",
        const=-1,
        default=None,
        metavar="N",
        help="Ejecutar escenarios (sin N = todos, con N = solo N escenarios)"
    )
    parser.add_argument(
        "-i", "--idiomas",
        action="store_true",
        help="Ejecutar solo preguntas relacionadas con idiomas"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Ejecutar todo: todas las preguntas + todos los escenarios"
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default=None,
        metavar="PREFIX",
        help="Prefijo para archivos de salida (uso interno)"
    )

    args = parser.parse_args()

    # Si no se especifica ninguna opción, mostrar ayuda
    if args.questions is None and args.scenarios is None and not args.all and not args.idiomas:
        parser.print_help()
        return

    # Determinar prefijos de salida
    questions_prefix = args.output if args.output else "benchmark"
    scenarios_prefix = args.output if args.output else "scenarios"

    # Ejecutar preguntas de idiomas
    if args.idiomas:
        idiomas_prefix = args.output if args.output else "benchmark_idiomas"
        run_benchmark(PREGUNTAS_IDIOMAS.copy(), idiomas_prefix)

    # Ejecutar preguntas
    if args.questions is not None or args.all:
        questions = PREGUNTAS_BENCHMARK.copy()
        if args.questions is not None and args.questions > 0:
            questions = questions[:args.questions]
        run_benchmark(questions, questions_prefix)

    # Ejecutar escenarios
    if args.scenarios is not None or args.all:
        scenarios = ESCENARIOS_CONVERSACION.copy()
        if args.scenarios is not None and args.scenarios > 0:
            scenarios = scenarios[:args.scenarios]
        run_scenario_benchmark(scenarios, scenarios_prefix)


if __name__ == "__main__":
    main()
