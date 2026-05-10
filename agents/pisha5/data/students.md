# Base de datos: students.db

Descripción:
Esta base de datos continene información de estudiantes de la Universidad de Málaga (UMA)

## Consideraciones generales
- Todas las tablas utilizan "id" como clave primaria salvo que se indique lo contrario.
- Las claves foráneas siguen el patrón {tabla}_id.
- Todas las relaciones están definidas mediante claves foráneas explícitas.

---

## Tabla: students

Descripción:
Información acerca de los estudiantes de la Universidad de Málaga

| Columna | Tipo | Restricciones | Descripción |
|----------|------|--------------|-------------|
| id | INTEGER | PRIMARY KEY | Identificador único del estudiante dentro de la base de datos |
| student_id | TEXT |  | Identificador oficial del estudiante. Puede ser un DNI, NIF número de pasaporte, etc. |
| name | TEXT |  | Nombre completo del estudiante (nombre y apellidos) |
| email | TEXT |  | Email del estudiante |
| username | TEXT |  | Nombre de usuario del estudiante usado para hacer login en el sistema |
| test | text |  | Variable de prueba del sistema. Todos los estudiantes contienen el texto TEST en esta columna |

---

