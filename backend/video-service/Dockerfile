FROM jockey-base:dev

WORKDIR /app

# Encoders + pipelines + services + everything else now live under main/.
# No more /workspace mount — the package is a normal Python tree inside /app.
ENV PYTHONPATH=/app:/shared

# uv (astral) — used for the laptop-side `pip install` of the service deps on
# top of jockey-base. Same convention as the GPU image and vast-bootstrap.sh.
RUN pip install --no-cache-dir uv

COPY backend/cm_shared /shared/cm_shared
COPY backend/video-service /app

# Service-local deps + lighthouse (with --no-deps; its numpy pin collides).
RUN uv pip install --system --no-cache -r /shared/requirements.txt -r /app/requirements.txt \
 && uv pip install --system --no-cache --no-deps \
      "lighthouse-mr @ git+https://github.com/line/lighthouse.git@main"

EXPOSE 1101

CMD ["sh", "-c", "alembic upgrade head && uvicorn main.main:app --host 0.0.0.0 --port 1101"]
