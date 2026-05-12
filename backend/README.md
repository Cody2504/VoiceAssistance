# tl-jockey backend

5 FastAPI services + Nginx gateway + Postgres / Redis / Qdrant / MinIO, mirroring the
shape of `/home/hai/project/ai-backend` for the video-assistant domain.

| Port | Service        | Owns                                                          |
| ---- | -------------- | ------------------------------------------------------------- |
| 85   | gateway        | Nginx; routes `/api/v1/*` to internal services                |
| 1100 | iam            | register, login, JWT renew, `/users/me`                        |
| 1101 | video-service  | upload, async indexing worker, grounding, search, qa, edit    |
| 1102 | agent-service  | LangGraph orchestration, SSE chat, conversation persistence   |
| 1103 | token-usage    | LLM call logging + per-user usage stats                       |

## Quick start

```bash
cp .env.example .env
make db-up         # postgres + redis + qdrant + minio
make local-up      # build & run all 5 services with live-reload + code mounts
```

App is live at `http://localhost:85/api/v1/health`. Frontend: `cd ../frontend && npm install && npm run dev` → `http://localhost:5173`.

## GPU mode

```bash
GROUNDING_DEVICE=cuda make gpu-up
```

Mount your trained checkpoint at `./.models/grounding/best.pt` (or update `GROUNDING_CHECKPOINT`).

## Service-to-service contracts

- All synchronous calls go over HTTP via container DNS (`http://video-service:1101/...`)
- Long-running indexing jobs go via Redis Queue (queue name `video_index`, consumer is `video-worker`)
- Agent stirrups call `video-service` for grounding/search/qa/edit; toggle Twelve Labs fallback with `STIRRUP_SEARCH=twelvelabs` / `STIRRUP_TEXTGEN=twelvelabs`

## Reused from `../jockey/`

The `video-service` and `agent-service` containers `pip install -e /workspace/jockey`, so changes
to `jockey/open_source/*` (model code) and `jockey/jockey_graph.py` are picked up live in dev.

- `jockey.open_source.indexer` — shot detection, frame extraction
- `jockey.open_source.{viclip_embedder, audio_encoder, metadata_encoder, asr_whisper}` — frozen encoders
- `jockey.open_source.training.grounding_head` — the trained head loaded by `video-service`
- `jockey.jockey_graph.Jockey` — subclassed by `agent-service` (`JockeyLocal`) to use HTTP-backed stirrups
- `jockey/prompts/*.md` — copied into `agent-service/main/prompts/`
