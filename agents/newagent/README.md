# Newagent

This is a new agente

**Tipo**: Agente RAG (Retrieval-Augmented Generation)

> ⚠️ **IMPORTANTE**: Los agentes RAG requieren Python 3.11, 3.12 o 3.13.
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

2. Añade tus documentos en `data/docs/` (formatos soportados: .txt, .md)

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
python cli.py newagent
```

## API Endpoints

- `GET /` - Información del agente
- `GET /health` - Health check
- `GET /examples` - Preguntas de ejemplo
- `POST /chat` - Enviar mensaje (busca contexto relevante automáticamente)
- `POST /reindex` - Reindexa los documentos (usar después de añadir nuevos)

### Ejemplo de uso con curl

```bash
# Chat normal
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "¿Qué información tienes sobre X?"}'

# Reindexar documentos
curl -X POST http://localhost:8000/reindex
```

## Estructura

```
newagent/
├── .env                # API key (no subir a git)
├── requirements.txt    # Dependencias
├── agent.py           # Lógica del agente con RAG
├── app.py             # Servidor FastAPI
├── run.sh             # Script de ejecución
└── data/
    ├── docs/          # Documentos a indexar (.txt, .md)
    └── chroma_db/     # Base de datos vectorial (se genera automáticamente)
```

## Cómo funciona

1. Al iniciar, el agente indexa todos los documentos en `data/docs/`
2. Cuando recibes una pregunta, busca los fragmentos más relevantes
3. Incluye ese contexto en el prompt para generar una respuesta informada
