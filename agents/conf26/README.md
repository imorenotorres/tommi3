# Novis B

Asistente de la conferencia de UNINOVIS

## Instalación

```bash
# Crear entorno virtual
python3 -m venv .venv
source .venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt
```

## Configuración

1. Copia tu API key de Mistral en `.env`:
```
MISTRAL_API_KEY=tu_api_key
```

2. Edita `data/data.md` con la información de tu agente.

## Ejecución

```bash
# Opción 1: Script automático
./run.sh

# Opción 2: Manual
source .venv/bin/activate
python app.py
```

El servidor estará disponible en http://localhost:8000

## API Endpoints

- `GET /` - Información del agente
- `GET /health` - Health check
- `GET /examples` - Preguntas de ejemplo
- `POST /chat` - Enviar mensaje

### Ejemplo de uso

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hola, ¿qué puedes hacer?"}'
```

## Estructura

```
conf26b/
├── .env                # API key (no subir a git)
├── requirements.txt    # Dependencias
├── agent.py           # Lógica del agente
├── app.py             # Servidor FastAPI
├── run.sh             # Script de ejecución
└── data/
    └── data.md        # Datos del agente
```
