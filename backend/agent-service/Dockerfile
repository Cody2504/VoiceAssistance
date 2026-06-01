FROM jockey-base:dev

WORKDIR /app

ENV PYTHONPATH=/app:/shared

COPY backend/cm_shared /shared/cm_shared
COPY backend/agent-service /app

EXPOSE 1102

CMD ["sh", "-c", "alembic upgrade head && uvicorn main.main:app --host 0.0.0.0 --port 1102"]
