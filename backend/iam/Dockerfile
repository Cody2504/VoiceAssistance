FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# cm_shared is mounted at /shared at build context; copy first for layer caching.
COPY ./cm_shared /shared/cm_shared
COPY ./cm_shared/requirements.txt /shared/requirements.txt

COPY ./iam/requirements.txt /app/requirements.txt
RUN pip install -r /shared/requirements.txt

COPY ./iam /app

ENV PYTHONPATH=/app:/shared

EXPOSE 1100

CMD ["sh", "-c", "alembic upgrade head && uvicorn main.main:app --host 0.0.0.0 --port 1100"]
