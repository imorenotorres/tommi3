# Base de datos: destinations.db

Descripción:
Esta base de datos contiene toda la información de los destinos disponibles y acuerdos de movilidad (interinstitutional agreements) para los estudiantes de la Universidad de Málaga (UMA). Contiene las condiciones, fechas, plazos, idiomas requeridos y requisitos de cada universidad de destino.

## Consideraciones generales
- Todas las tablas utilizan "id" como clave primaria salvo que se indique lo contrario.
- Las claves foráneas siguen el patrón {tabla}_id.
- Todas las relaciones están definidas mediante claves foráneas explícitas.

---

## Tabla: destinations

Descripción:
Acuerdos de movilidad interinstitucional que definen las opciones de destino para los alumnos. Aglutina de forma textual y comprensible las reglas de plazas, tutores, centros y requisitos de idioma para que pueda ser interpretado fácilmente de un vistazo.

| Columna | Tipo | Restricciones | Descripción |
|----------|------|--------------|-------------|
| id | INTEGER | PRIMARY KEY | Identificador único interno en base de datos. Usar para joins. |
| agreement_id | TEXT |  | Código numérico oficial del acuerdo. Útil para identificar el acuerdo exacto en convocatorias. |
| start_date | TEXT |  | Fecha de inicio de vigencia del acuerdo de movilidad. |
| end_date | TEXT |  | Fecha de finalización de vigencia del acuerdo de movilidad. |
| mobility_program | TEXT |  | Programa de movilidad al que pertenece (ej. Erasmus+ KA131, Plan Propio, etc). |
| host_institution | TEXT |  | Nombre de la Universidad o Institución de acogida/destino. |
| destination_country | TEXT |  | País donde se encuentra la universidad de destino. |
| destination_faculty | TEXT |  | Facultad, departamento o escuela de la universidad de destino que acoge al estudiante. |
| isced_codes | TEXT |  | Códigos ISCED que definen las áreas de estudio permitidas en este acuerdo. |
| uma_faculties | TEXT |  | Centros o Facultades de la UMA que tienen permitido enviar estudiantes a este acuerdo. |
| uma_degrees | TEXT |  | Titulaciones concretas de la UMA que pueden aplicar a este acuerdo. |
| lang_1_name | TEXT |  | Nombre del primer idioma requerido (ej. Inglés, Francés). NULL si no se exige idioma. |
| lang_1_level | TEXT |  | Nivel del primer idioma requerido (ej. B1, B2, C1). |
| lang_1_cert_mandatory | TEXT |  | Indica si es obligatorio presentar un certificado oficial para el primer idioma (Sí/No). |
| lang_1_cert_details | TEXT |  | Detalles de los certificados aceptados para el primer idioma. |
| lang_2_name | TEXT |  | Nombre del segundo idioma requerido, en caso de haberlo. NULL si solo pide un idioma. |
| lang_2_level | TEXT |  | Nivel del segundo idioma requerido. |
| lang_2_cert_mandatory | TEXT |  | Indica si es obligatorio presentar certificado para el segundo idioma (Sí/No). |
| lang_2_cert_details | TEXT |  | Detalles de los certificados aceptados para el segundo idioma. |
| allows_undergraduate | TEXT |  | Indica si el acuerdo permite a estudiantes de Grado solicitar plaza (Sí/No). |
| allows_master | TEXT |  | Indica si el acuerdo permite a estudiantes de Máster solicitar plaza (Sí/No). |
| allows_phd | TEXT |  | Indica si el acuerdo permite a estudiantes de Doctorado solicitar plaza (Sí/No). |
| min_gpa_requirement | REAL |  | Nota media mínima requerida (GPA) para poder solicitar la plaza. NULL si no hay límite de nota media. |
| student_vacancies | TEXT |  | Información sobre las plazas disponibles para estudiantes. Incluye el número de plazas, duración máxima en meses y periodos permitidos (ej. SM1, SM2, FY). |
| tutors | TEXT |  | Información sobre qué tutor o tutores académicos se encargan de gestionar este acuerdo en origen. |
| academic_requirements_text | TEXT |  | Información de texto libre escrita por el coordinador detallando requisitos académicos extra (ej. créditos mínimos superados). |
| public_comments | TEXT |  | Observaciones públicas y advertencias importantes para los estudiantes interesados en este destino. |
| internal_comments | TEXT |  | Anotaciones internas del personal de relaciones internacionales de la UMA. |

---

