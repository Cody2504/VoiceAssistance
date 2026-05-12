FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY ./cm_shared /shared/cm_shared
COPY ./cm_shared/requirements.txt /shared/requirements.txt
COPY ./token-usage/requirements.txt /app/requirements.txt
RUN pip install -r /shared/requirements.txt

COPY ./token-usage /app

ENV PYTHONPATH=/app:/shared
EXPOSE 1103

CMD ["sh", "-c", "alembic upgrade head && uvicorn main.main:app --host 0.0.0.0 --port 1103"]
