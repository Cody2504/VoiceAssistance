FROM jockey-base:dev

WORKDIR /app

ENV PYTHONPATH=/app:/shared

# The LangGraph Postgres checkpointer (Phase 1) needs these on top of the base
# image, which only ships the sqlite checkpoint backend. The base venv is a uv
# venv WITHOUT its own pip, and bare `pip` resolves to the system interpreter —
# so packages land outside /opt/venv and aren't importable at runtime. Bootstrap
# pip INTO the venv (ensurepip) and install with the venv's own python.
RUN /opt/venv/bin/python -m ensurepip --upgrade && \
    /opt/venv/bin/python -m pip install --no-cache-dir \
    "langgraph-checkpoint-postgres==2.0.2" \
    "psycopg[binary]==3.2.3" \
    "psycopg-pool==3.2.4" \
    "deepeval==4.0.6"

# Ship the agent_eval harness + deepeval so the admin Evaluation dashboard can
# run evals in-process (the COPY below also brings agent_eval/ into the image).

COPY backend/cm_shared /shared/cm_shared
COPY backend/agent-service /app

EXPOSE 1102

CMD ["sh", "-c", "alembic upgrade head && uvicorn main.main:app --host 0.0.0.0 --port 1102"]
