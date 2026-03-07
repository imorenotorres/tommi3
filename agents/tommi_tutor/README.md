# Tommi virtual tutor

Your virtual tutor to learn the basics of AI Agents development with Tommi, and somme advanced options also

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

Para usar un puerto diferente: `PORT=8001 ./run.sh`

## Interacción por terminal

También puedes interactuar directamente desde el terminal sin servidor web:

```bash
cd web
source .venv/bin/activate
python cli.py tommi_tutor
```

## API Endpoints

- `GET /` - Información del agente
- `GET /health` - Health check
- `GET /examples` - Preguntas de ejemplo
- `POST /chat` - Enviar mensaje

### Ejemplo de uso con curl

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hola, ¿qué puedes hacer?"}'
```

## Estructura

```
tommi_tutor/
├── .env                # API key (no subir a git)
├── requirements.txt    # Dependencias
├── agent.py           # Lógica del agente
├── app.py             # Servidor FastAPI
├── run.sh             # Script de ejecución
└── data/
    └── data.md        # Datos del agente
```
