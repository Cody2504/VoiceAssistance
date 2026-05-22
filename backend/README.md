# tl-jockey backend

5 FastAPI services + Nginx gateway + Postgres / Redis / Qdrant / MinIO, mirroring the
shape of `/home/hai/project/ai-backend` for the video-assistant domain.

| Port (host) | Service        | Owns                                                          |
| ----------- | -------------- | ------------------------------------------------------------- |
| 8085*       | gateway        | Nginx; routes `/api/v1/*` to internal services                |
| 1100        | iam            | register, login, JWT renew, `/users/me`                       |
| 1101        | video-service  | upload, async indexing worker, grounding, search, qa, edit    |
| 1102        | agent-service  | LangGraph orchestration, SSE chat, conversation persistence   |
| 1103        | token-usage    | LLM call logging + per-user usage stats                       |
| 9000/9001   | minio          | S3-compatible object store + console                          |

\*Override with `GATEWAY_PORT=85` in `.env` if you don't have the Fsoft work-platform
stack running on this host.

Postgres and Redis are published on **non-default** host ports (`15432` / `16379`) so
they coexist with the Fsoft work-platform stack's own postgres/redis on `5432` / `6379`.
Qdrant is not published — only services on `jockey-net` use it. Agent-service runs in
`network_mode: host` (workaround for host iptables blocking egress from docker bridge
networks); it reaches postgres/redis via the published host ports, and reaches the
other app services via their `1100`-`1103` host publishes.

## Quick start

```bash
cp .env.example .env
# Fill in: OPENAI_API_KEY (or AZURE_OPENAI_*), OPENROUTER_API_KEY, HF_API_KEY

make base-build           # one-time: builds jockey-base:dev locally (~5-10 min, heavy)
docker compose build      # ~30s: only service code layers on top of the local base
docker compose up         # everything starts in order via healthchecks
```

After the first `make base-build`, the steady-state dev loop is just the last two
commands. Rebuild the base only when you change `base_image/{Dockerfile,requirements.txt,build-constraints.txt}`.

App is live at `http://localhost:8085/api/v1/health` (or `GATEWAY_PORT` value).
Frontend: `cd ../frontend && npm install && npm run dev` → `http://localhost:5173`.

### Prerequisites

- Docker 24+ with Compose v2
- `.models/grounding/best.pt` — your trained grounding head (mount target inside `video-service`)
- `../third_party/qd_detr/` — vendored repo (mount target inside `video-service`)

If either path is missing the bind mount will be an empty directory and video-service
will crash on first request. Create empty placeholders if you only want to smoke-test
the chat path without grounding.

## Base image (`jockey-base:dev`)

All heavy Python deps (torch-cpu, transformers, whisper, langchain, langgraph, fastapi,
sqlalchemy, …) live in a single multi-stage image at `./base_image`, kept **local-only**
(not pushed to any registry). Per-service Dockerfiles `FROM jockey-base:dev` and only
`COPY` source code — editing any service's Python file rebuilds in ~2 seconds.

Rebuild the base when you change one of:

- `base_image/Dockerfile`
- `base_image/requirements.txt`
- `base_image/build-constraints.txt`

```bash
make base-build           # → jockey-base:dev in the local docker image store
```

That's it — no registry push, no login required.

## Dev loop (hot reload)

```bash
make local-up
```

This stacks `docker-compose.yml + docker-compose.local.yml`, mounting each service's
source directory and re-running uvicorn with `--reload`. Edits to `*.py` apply in
~1 second without a rebuild.

## GPU mode

```bash
GROUNDING_DEVICE=cuda make gpu-up
```

Mount your trained checkpoint at `./.models/grounding/best.pt` (or set `GROUNDING_CHECKPOINT`).

## Service-to-service contracts

- All synchronous calls go over HTTP via container DNS (`http://video-service:1101/...`)
- Long-running indexing jobs go via Redis Queue (queue name `video_index`, consumer is `video-worker`)
- Agent stirrups call `video-service` for grounding/search/qa/edit; toggle Twelve Labs fallback with `STIRRUP_SEARCH=twelvelabs` / `STIRRUP_TEXTGEN=twelvelabs`

## Reused from `../jockey/`

The `video-service` and `agent-service` containers mount `../jockey` at `/workspace/jockey`
and expose it via `PYTHONPATH=/workspace`. The package's PyPI deps are pre-installed in
`jockey-base`, so we don't `pip install -e` it — module-level edits to `jockey/*.py` are
picked up after a service rebuild or, in `local-up` dev mode, on hot reload.

- `jockey.open_source.indexer` — shot detection, frame extraction
- `jockey.open_source.{viclip_embedder, audio_encoder, metadata_encoder, asr_whisper}` — frozen encoders
- `jockey.open_source.training.grounding_head` — the trained head loaded by `video-service`
- `jockey.jockey_graph.Jockey` — subclassed by `agent-service` (`JockeyLocal`) to use HTTP-backed stirrups
- `jockey/prompts/*.md` — copied into `agent-service/main/prompts/`

## Troubleshooting

| Symptom                                                           | Fix                                                                       |
| ----------------------------------------------------------------- | ------------------------------------------------------------------------- |
| `failed to resolve image jockey-base:dev`                         | Run `make base-build` first — base image is local-only, not pulled from a registry |
| `port 8085 already in use`                                        | Set `GATEWAY_PORT=8086` (or any free port) in `.env`                      |
| `port 15432 / 16379 already in use`                               | Pick another free host port in `docker-compose.yml` (postgres/redis ports + agent-service `POSTGRES_PORT` / `REDIS_PORT` env overrides) |
| `agent-service: connection refused to localhost:1101`             | Confirm video-service host publish on `1101` is up (`docker compose ps`)  |
| `alembic.util.exc.CommandError: ... could not connect to server`  | Wait — services now block on `postgres: service_healthy`; first up is ~10s|
| `video-service crashes: FileNotFoundError /models/grounding/...`  | Provide `./.models/grounding/best.pt` or set `GROUNDING_BACKEND=disabled` |
| `MinIO: bucket does not exist`                                    | `minio-init` runs once and exits; `docker compose up minio-init` to rerun |
