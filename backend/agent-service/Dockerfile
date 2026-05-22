FROM jockey-base:dev

WORKDIR /app

ENV PYTHONPATH=/app:/shared:/workspace

COPY backend/cm_shared /shared/cm_shared
COPY pyproject.toml /workspace/pyproject.toml
COPY backend/agent-service /app

EXPOSE 1102

CMD ["sh", "-c", "alembic upgrade head && uvicorn main.main:app --host 0.0.0.0 --port 1102"]
