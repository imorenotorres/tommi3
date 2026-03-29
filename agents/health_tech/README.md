# Health and social technology

Description

**Tipo**: Agente RAG+Metadata (Retrieval-Augmented Generation with Metadata)

> ⚠️ **IMPORTANTE**: Los agentes RAG+Metadata requieren Python 3.11, 3.12 o 3.13.
> ChromaDB **no es compatible con Python 3.14+**. Si ves el error 307, usa una versión anterior de Python.

## Instalación

```bash
# Crear entorno virtual (requiere Python 3.11-3.13)
python3.12 -m venv .venv  # o python3.13, python3.11
source .venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt
```

## Configuración

1. Copia tu API key de Mistral en `.env`:
```
MISTRAL_API_KEY=tu_api_key
```

2. Añade tus documentos en `data/docs/` (formatos soportados: .txt, .md, .pdf)

3. (Opcional) Configura campos de metadatos personalizados en `data/metadata.json`

## Ejecución

```bash
# Opción 1: Script automático
./run.sh

# Opción 2: Manual
source .venv/bin/activate
python app.py
```

El servidor estará disponible en http://localhost:8000

Para usar un puerto diferente: `PORT=8001 ./run.sh`

## Interacción por terminal

También puedes interactuar directamente desde el terminal sin servidor web:

```bash
cd web
source .venv/bin/activate
python cli.py health_tech
```

## API Endpoints

- `GET /` - Información del agente
- `GET /health` - Health check
- `GET /examples` - Preguntas de ejemplo
- `GET /metadata` - Metadatos de todos los documentos indexados
- `POST /chat` - Enviar mensaje (busca contexto relevante con metadatos)
- `POST /reindex` - Reindexa los documentos con metadatos

### Ejemplo de uso con curl

```bash
# Chat normal
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "¿Qué información tienes sobre X?"}'

# Ver metadatos de documentos
curl http://localhost:8000/metadata

# Reindexar documentos
curl -X POST http://localhost:8000/reindex
```

## Metadatos

Los metadatos se extraen automáticamente de los documentos:

| Campo | PDF | TXT/MD |
|-------|-----|--------|
| title | Del PDF o nombre de archivo | Nombre de archivo |
| author | Del PDF | - |
| date | Del PDF | - |
| page_count | Sí | - |
| file_size | Sí | Sí |
| file_type | Sí | Sí |

### Configuración personalizada de metadatos

Puedes personalizar los campos de metadatos creando `data/metadata.json`:

```json
{
    "fields": ["title", "author", "date", "file_type", "file_size", "page_count", "department", "category"]
}
```

## Estructura

```
health_tech/
├── .env                # API key (no subir a git)
├── requirements.txt    # Dependencias
├── agent.py           # Lógica del agente con RAG+Metadata
├── app.py             # Servidor FastAPI
├── run.sh             # Script de ejecución
└── data/
    ├── docs/          # Documentos a indexar (.txt, .md, .pdf)
    ├── metadata.json  # (Opcional) Configuración de campos de metadatos
    └── chroma_db/     # Base de datos vectorial (se genera automáticamente)
```

## Cómo funciona

1. Al iniciar, el agente indexa todos los documentos en `data/docs/` extrayendo contenido y metadatos
2. Los metadatos (autor, título, fecha, etc.) se almacenan junto a cada chunk en ChromaDB
3. Cuando recibes una pregunta, busca los fragmentos más relevantes
4. El LLM recibe tanto el contenido relevante como los metadatos para generar respuestas informadas
5. Las preguntas sobre metadatos (e.g., "¿qué documentos hay de tal autor?") se responden usando la información de metadatos
