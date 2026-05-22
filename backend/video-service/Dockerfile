FROM jockey-base:dev

WORKDIR /app

# jockey is exposed on PYTHONPATH instead of being pip-installed; its
# dependencies are already in the base venv.
ENV PYTHONPATH=/app:/shared:/workspace

COPY backend/cm_shared /shared/cm_shared
COPY jockey /workspace/jockey
COPY pyproject.toml /workspace/pyproject.toml
COPY backend/video-service /app

EXPOSE 1101

CMD ["sh", "-c", "alembic upgrade head && uvicorn main.main:app --host 0.0.0.0 --port 1101"]
