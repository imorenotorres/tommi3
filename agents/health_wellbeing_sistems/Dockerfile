FROM python:3.12-slim

WORKDIR /app

# Copy shared web modules needed by the agent
COPY web/llm_client.py /app/web/llm_client.py
COPY web/error_codes.py /app/web/error_codes.py

# Copy agent files
COPY agents/health_wellbeing_sistems/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY agents/health_wellbeing_sistems/agent.py /app/agent.py
COPY agents/health_wellbeing_sistems/app.py /app/app.py
COPY agents/health_wellbeing_sistems/config.json /app/config.json

# Copy data
COPY agents/health_wellbeing_sistems/data /app/data

# Default environment (can be overridden via docker-compose or -e flags)
ENV LLM_PROVIDER=mistral
ENV MISTRAL_MODEL=mistral-small-latest
ENV RAG_APPROACH=context_preserving
ENV PORT=8000

EXPOSE 8000

CMD ["python", "app.py"]
