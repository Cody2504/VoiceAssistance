# syntax=docker/dockerfile:1.7
#
# jockey-base: shared base image for all tl-jockey FastAPI services.
# Mirrors the ai-backend/base_image pattern: multi-stage build, uv installer,
# BuildKit cache mount for wheels, torch installed from the CPU index, and a
# trimmed runtime image with no compilers.
#
# Build with:   docker build -t jockey-base:dev ./backend/base_image
# Or:           make base-build

############################
# 1) Python deps builder
############################
FROM python:3.11-slim AS builder

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    VENV_PATH=/opt/venv \
    UV_LINK_MODE=copy

WORKDIR /app

# Compilers + headers needed to build wheels that aren't published as binaries
# for python:3.11-slim (e.g. psycopg2-binary fallbacks, decord on some arches).
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        g++ \
        pkg-config \
        git \
        libffi-dev \
        libssl-dev \
        libpq-dev \
        libsndfile1-dev \
        ca-certificates \
        curl \
 && rm -rf /var/lib/apt/lists/*

# uv: parallel pip-compatible installer. Much faster than pip on cold installs.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY requirements.txt build-constraints.txt /tmp/

RUN uv venv ${VENV_PATH}
ENV PATH="${VENV_PATH}/bin:${PATH}"

# Two-step install:
#   1. torch + torchvision from the CPU index. This avoids pulling nvidia-cu12-*
#      wheels (~700 MB) that we don't use.
#   2. Everything else under a build-time setuptools<80 constraint so the
#      openai-whisper sdist (which imports pkg_resources) can still build.
#
# The cache mount at /root/.cache/uv survives between builds, so editing
# requirements.txt re-uses already-downloaded wheels instead of re-fetching.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --python ${VENV_PATH}/bin/python \
        --index-url https://download.pytorch.org/whl/cpu \
        torch==2.4.1 torchvision==0.19.1 \
 && uv pip install --python ${VENV_PATH}/bin/python \
        --build-constraint /tmp/build-constraints.txt \
        -r /tmp/requirements.txt \
 && rm -rf ${VENV_PATH}/include \
 && find ${VENV_PATH} -type d -name '__pycache__' -prune -exec rm -rf '{}' + \
 && find ${VENV_PATH} -type f -name '*.a' -delete


############################
# 2) Runtime image
############################
FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    VENV_PATH=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    HF_HOME=/models/.hf \
    TRANSFORMERS_CACHE=/models/.hf \
    TORCH_HOME=/models/.torch

# Runtime-only libs (no compilers): ffmpeg + libsndfile for whisper/decord,
# libpq for psycopg2, libgl/libglib for opencv-python (scenedetect dep).
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        libsndfile1 \
        libpq5 \
        libgl1 \
        libglib2.0-0 \
        ca-certificates \
        curl \
 && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app

CMD ["bash"]
