FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg git build-essential \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY ./cm_shared /shared/cm_shared
COPY ./cm_shared/requirements.txt /shared/requirements.txt

COPY ./agent-service/requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

COPY ./jockey /workspace/jockey
RUN pip install -e /workspace || true

COPY ./agent-service /app

ENV PYTHONPATH=/app:/shared:/workspace

EXPOSE 1102

CMD ["sh", "-c", "alembic upgrade head && uvicorn main.main:app --host 0.0.0.0 --port 1102"]
