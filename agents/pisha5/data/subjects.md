# Base de datos: subjects.db

Descripción:
Esta base de datos continene información acerca de los estudiantes matriculados en la Universidad de Málaga (UMA) durante el curso 2025/26

## Consideraciones generales
- Todas las tablas utilizan "id" como clave primaria salvo que se indique lo contrario.
- Las claves foráneas siguen el patrón {tabla}_id.
- Todas las relaciones están definidas mediante claves foráneas explícitas.

---

## Tabla: degree

Descripción:
Titulaciones disponibles en la Universidad de Málaga.

| Columna | Tipo | Restricciones | Descripción |
|----------|------|--------------|-------------|
| id | INTEGER | PRIMARY KEY | Identificador único de una asignatura en esta base de datos |
| name | TEXT |  | Nombre de la titulación |

---

## Tabla: subjects

Descripción:
Asignaturas de la Universidad de Málaga en el curso 2025/26

| Columna | Tipo | Restricciones | Descripción |
|----------|------|--------------|-------------|
| id | INTEGER | PRIMARY KEY | Identificador único de una asignatura en esta base de datos |
| name | TEXT |  | Nombre de la asignatura |
| subject_code | TEXT |  | Código de la asignatura. Conocido también como código PROA.Cada asignatura dentro de una misma titulación tiene un código diferente.La primera cifra de este código indica el curso en el cual se imparte. e.g: 304 es una asignatura de tercer curso.Si la primera cifra es 8 o 9, entonces se trata de una asignatura optativa que no está asignada a ningún curso concreto |
| degree_id | INTEGER | FK → degree.id | Lláve foránea a la tabla degree. Las asignaturas están vinculadas a una titulación mediante este campo |
| degree_code | TEXT |  | Código de la titulación. Solo es útil a título informativo |

### Relaciones

- subjects.degree_id → degree.id

---

