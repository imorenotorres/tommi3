# Pisha2

Asistente Pisha2

**Tipo**: Agente Text-to-SQL (Consultas en lenguaje natural)

## Cómo funciona

Este agente convierte preguntas en lenguaje natural a consultas SQL:

1. **Análisis**: El LLM analiza tu pregunta y el esquema de la base de datos
2. **Generación SQL**: Convierte la pregunta a una consulta SQL válida
3. **Ejecución**: Ejecuta la consulta en la base de datos SQLite local
4. **Formateo**: El LLM presenta los resultados de forma clara y amigable

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
pisha2/
├── .env                # API key (no subir a git)
├── requirements.txt    # Dependencias
├── agent.py           # Lógica Text-to-SQL
├── app.py             # Servidor FastAPI
├── run.sh             # Script de ejecución
└── data/
    └── database.db    # Base de datos SQLite (debes crearla)
```

## Seguridad

El agente solo permite consultas SELECT por seguridad:
- No se pueden ejecutar INSERT, UPDATE, DELETE
- No se permite DROP, CREATE, ALTER
- Los comentarios SQL (--) están bloqueados

## Consejos

- **Esquema claro**: Usa nombres de tablas y columnas descriptivos
- **Datos de ejemplo**: Añade algunos registros para probar
- **Preguntas específicas**: Cuanto más específica la pregunta, mejor el SQL generado
