# All Python deps live in jockey-base. This Dockerfile only ships source code,
# so iam rebuilds in ~2s whenever you edit anything under iam/.
FROM jockey-base:dev

WORKDIR /app

ENV PYTHONPATH=/app:/shared

COPY backend/cm_shared /shared/cm_shared
COPY backend/iam /app

EXPOSE 1100

CMD ["sh", "-c", "alembic upgrade head && uvicorn main.main:app --host 0.0.0.0 --port 1100"]
