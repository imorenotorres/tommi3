FROM python:3.12-slim

WORKDIR /app

# System dependencies for chromadb and sentence-transformers
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy shared web modules needed by the agent
COPY web/llm_client.py /app/web/llm_client.py
COPY web/error_codes.py /app/web/error_codes.py

# Copy agent files
COPY agents/responsible_ai/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY agents/responsible_ai/agent.py /app/agent.py
COPY agents/responsible_ai/app.py /app/app.py
COPY agents/responsible_ai/config.json /app/config.json

# Copy data (docs, metadata, papers JSONs, researchers)
# ChromaDB will be rebuilt on first run if not mounted
COPY agents/responsible_ai/data /app/data

# Default environment (can be overridden via docker-compose or -e flags)
ENV LLM_PROVIDER=mistral
ENV MISTRAL_MODEL=mistral-small-latest
ENV RAG_APPROACH=context_preserving
ENV VERIFY_GROUNDING=false
ENV PORT=8000

EXPOSE 8000

CMD ["python", "app.py"]
