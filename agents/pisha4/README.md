# Pisha2

Asistente Pisha2

**Tipo**: Agente Text-to-SQL (Consultas en lenguaje natural)

## Cómo funciona

Este agente convierte preguntas en lenguaje natural a consultas SQL:

1. **Análisis**: El LLM analiza tu pregunta y el esquema de la base de datos
2. **Generación SQL**: Convierte la pregunta a una consulta SQL válida
3. **Verificación**: El SQL generado se verifica antes de ejecutarse (see below)
4. **Ejecución**: Ejecuta la consulta en la base de datos SQLite local
5. **Formateo**: Python presenta los resultados de forma clara y amigable

## SQL Verification System (`sql_verifier.py`)

Pisha4 includes a multi-layer SQL verification system that checks every generated query **before and after execution**. This prevents hallucinated or misaligned SQL from reaching the database.

### Schema Verification

- Validates all table and column names against the actual database schema
- Detects dangerous keywords (INSERT, DELETE, DROP, etc.)
- Flags overly broad queries (SELECT *, excessive OR+LIKE conditions)
- Checks country names are searched in the correct column (`destination_country`)

### Semantic Alignment Check

Verifies that the generated SQL actually matches the user's question:

- Extracts key terms from the user's question (filtering stop words)
- Extracts string literals from the SQL's WHERE clauses
- Checks if question terms appear in the SQL values
- Supports **cross-language equivalences** (e.g. "english" ↔ "inglés", "finland" ↔ "finlandia", "libya" ↔ "libia")
- Ignores intent words ("requiring", "available", "minimum") that describe query logic, not data values

**Example:** If the user asks "Show all agreements with Libia" but the LLM generates SQL searching for English B1 language requirements, the semantic check detects the mismatch and blocks execution.

### Prompt Level Enforcement

Controlled by `prompt_level` in `config.json`:

- **`stringent`** (default): Blocks execution on hard errors (unknown tables/columns, dangerous keywords, semantic mismatch)
- **`tolerant`**: Logs warnings but allows execution to proceed

### Reliability Badge

After execution, a reliability badge is generated showing:
- Confidence percentage based on schema validation + semantic alignment
- Verified vs unknown tables and columns
- Any issues detected (shown in crystal_box transparency mode)

### Transparency Levels

Controlled by `transparency_level` in `config.json`:

- **`crystal_box`**: Shows SQL query + full verification details + reliability badge
- **`grey_box`**: Shows SQL query + badge (summary only)
- **`black_box`**: Shows results only (no SQL, no badge)

## Instalación

```bash
# Crear entorno virtual
python3 -m venv .venv
source .venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt
```

## Configuración

1. Configura tu LLM en `.env`:
```
MISTRAL_API_KEY=tu_api_key
```

2. **IMPORTANTE**: Crea tu base de datos SQLite en `data/database.db`:
```bash
# Ejemplo: crear base de datos desde un archivo SQL
sqlite3 data/database.db < tu_esquema.sql

# O crear tablas manualmente
sqlite3 data/database.db << 'EOF'
CREATE TABLE clientes (
    id INTEGER PRIMARY KEY,
    nombre TEXT NOT NULL,
    email TEXT,
    ciudad TEXT
);

INSERT INTO clientes VALUES (1, 'Ana García', 'ana@email.com', 'Madrid');
INSERT INTO clientes VALUES (2, 'Carlos López', 'carlos@email.com', 'Barcelona');
EOF
```

## Ejecución

```bash
# Opción 1: Script automático
./run.sh

# Opción 2: Manual
source .venv/bin/activate
python app.py
```

El servidor estará disponible en http://localhost:8000

## Ejemplos de uso

Una vez configurada la base de datos, puedes hacer preguntas como:

- "¿Cuántos clientes hay en total?"
- "Muéstrame los clientes de Madrid"
- "¿Cuál es el producto más vendido?"
- "Dame las ventas del último mes ordenadas por fecha"

### Con curl

```bash
# Pregunta simple
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "¿Cuántos registros hay en la tabla clientes?"}'

# Ver el esquema de la BD
curl http://localhost:8000/schema
```

## Interacción por terminal

```bash
cd web
source .venv/bin/activate
python cli.py pisha2
```

## API Endpoints

- `GET /` - Información del agente
- `GET /health` - Health check
- `GET /schema` - Ver esquema de la base de datos
- `GET /examples` - Preguntas de ejemplo
- `POST /chat` - Enviar pregunta en lenguaje natural

## Estructura

```
pisha4/
├── .env                # API key (no subir a git)
├── config.json         # Agent configuration (transparency, prompt level, audit)
├── requirements.txt    # Dependencias
├── agent.py           # Lógica Text-to-SQL + verification integration
├── sql_verifier.py    # SQL schema + semantic verification engine
├── app.py             # Servidor FastAPI
├── run.sh             # Script de ejecución
└── data/
    ├── database.db    # Base de datos SQLite
    ├── database_schema.md  # Schema documentation
    └── audit_log.jsonl     # EU AI Act audit trail (if enabled)
```

## Seguridad

El agente solo permite consultas SELECT por seguridad:
- No se pueden ejecutar INSERT, UPDATE, DELETE
- No se permite DROP, CREATE, ALTER
- Los comentarios SQL (--) están bloqueados
- Schema verification prevents queries on non-existent tables/columns
- Semantic alignment prevents executing SQL that doesn't match the user's question

## Consejos

- **Esquema claro**: Usa nombres de tablas y columnas descriptivos
- **Datos de ejemplo**: Añade algunos registros para probar
- **Preguntas específicas**: Cuanto más específica la pregunta, mejor el SQL generado
