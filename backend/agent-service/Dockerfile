FROM jockey-base:dev

WORKDIR /app

ENV PYTHONPATH=/app:/shared

# The LangGraph Postgres checkpointer (Phase 1) needs these on top of the base
# image, which only ships the sqlite checkpoint backend. The base venv is a uv
# venv without its own pip, and bare `pip` is the system interpreter's — target
# the venv explicitly or the packages land in the wrong site-packages.
RUN pip --python /opt/venv/bin/python install --no-cache-dir \
    "langgraph-checkpoint-postgres==2.0.2" \
    "psycopg[binary]==3.2.3" \
    "psycopg-pool==3.2.4"

COPY backend/cm_shared /shared/cm_shared
COPY backend/agent-service /app

EXPOSE 1102

CMD ["sh", "-c", "alembic upgrade head && uvicorn main.main:app --host 0.0.0.0 --port 1102"]
