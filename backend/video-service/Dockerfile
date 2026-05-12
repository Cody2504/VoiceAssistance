# Default base — CPU-friendly. Override with a CUDA base via build arg for GPU.
ARG BASE_IMAGE=python:3.11-slim
FROM ${BASE_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/models/.hf \
    TRANSFORMERS_CACHE=/models/.hf \
    TORCH_HOME=/models/.torch

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg git build-essential libsndfile1 \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Layer 1: shared lib
COPY ./cm_shared /shared/cm_shared
COPY ./cm_shared/requirements.txt /shared/requirements.txt

# Layer 2: service deps
COPY ./video-service/requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

# Layer 3: jockey package (editable — mounted in dev, copied here for prod)
COPY ./jockey /workspace/jockey
COPY ./pyproject.toml /workspace/pyproject.toml 2>/dev/null || true
RUN pip install -e /workspace || true

# Layer 4: service code
COPY ./video-service /app

ENV PYTHONPATH=/app:/shared:/workspace

EXPOSE 1101

CMD ["sh", "-c", "alembic upgrade head && uvicorn main.main:app --host 0.0.0.0 --port 1101"]
