FROM jockey-base:dev

WORKDIR /app

ENV PYTHONPATH=/app:/shared

COPY backend/cm_shared /shared/cm_shared
COPY backend/token-usage /app

EXPOSE 1103

CMD ["sh", "-c", "alembic upgrade head && uvicorn main.main:app --host 0.0.0.0 --port 1103"]
