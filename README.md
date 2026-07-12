# VideoAssistance

A self-hosted, open-source **video understanding platform** — upload a video and
then search it, ground it ("when does X happen?"), summarize it, ask questions
about it, moderate it, and edit it, all through a conversational agent and a web
console. It mirrors the product shape of Twelve Labs' **Marengo** (video
retrieval) and **Pegasus** (video text generation), but runs entirely on
**self-hosted open-source models** — no dependency on any closed video SaaS.

> **ATTENTION**: This is alpha-stage research/product software and may break or
> behave unexpectedly.

The project began as a fork of the [Jockey](https://python.langchain.com/v0.1/docs/langgraph/)
LangGraph video agent (the original reference package still lives under
[`jockey/`](jockey/)) and grew into a full microservice platform under
[`backend/`](backend/) with a React frontend under [`frontend/`](frontend/). The
internal codename **jockey** persists throughout the stack (`jockey-net`,
`jockey-base:dev`, the `jockey_*` Qdrant collections).

---

## What it can do

| Capability | Endpoint (video-service) | Behind it |
| --- | --- | --- |
| **Visual search** — "find any moment a player dunks" | `POST /videos/search` | CLIP-L embeddings over `jockey_shots` |
| **Text / OCR / transcript search** | `POST /videos/search/text` | `text-embedding-3-large` over captions + ASR + on-screen text |
| **Image-as-query search** — "which video is this frame from?" | `POST /videos/search/image` | Multi-signal fusion: CLIP-L + DINOv2 + region crops + OCR + VLM visual-entities |
| **Motion / action search** — "pouring", "dunking" | `POST /videos/search/motion` | ViCLIP temporal embeddings |
| **Grounding** — "when does X happen?" (sub-second) | `POST /videos/{id}/ground` | InternVideo2 features → trained **SG-DETR / MRDETR** head (Lighthouse CG-DETR/QD-DETR fallback) |
| **When (fan-out localizer)** | `POST /videos/{id}/when` | 8-stream fusion (visual, event, segment, OCR, audio, motion, grounding-refine) + optional GroundingDINO object verify |
| **Highlights** — query-free saliency reel | `GET /videos/{id}/highlights` | IV2 per-clip saliency / QD-DETR-CLAP for audio |
| **Standing timeline** — speakers, sounds, on-screen text, actions | `GET /videos/{id}/timeline` | 7 event generators persisted to Postgres + `jockey_timeline_events` |
| **Q&A / summarize / describe** | `POST /videos/{id}/qa` | Qwen3-VL (multimodal — reads pixels of cited frames, not just OCR) |
| **Content moderation** | `POST /videos/{id}/moderate` | Falconsai NSFW ViT + toxic-bert / violence classifier |
| **Sound search** | `GET /videos/{id}/sounds?tag=Laughter` | PANN CNN14 (527 AudioSet classes) |
| **Recommend similar** | `GET /videos/{id}/recommend` | Mean-pooled per-video vector over `jockey_videos` |
| **Edit** — cut + concatenate clips | `POST /videos/{id}/edit` | ffmpeg |

Everything above is also reachable in natural language through the **agent**, and
via point-and-click demo tiles in the **Playground**.

---

## Architecture

A Nginx gateway fronts several FastAPI microservices plus a React SPA, backed by
Postgres / Redis / Qdrant / MinIO (S3). The GPU-heavy `video-service` can run
co-located or on a separate GPU box.

```
                         ┌──────────────────────────┐
   Browser ──────────────►  frontend (React 19/Vite) │  Cloudflare Pages
                         └────────────┬─────────────┘
                                      │ /api/v1/*
                         ┌────────────▼─────────────┐
                         │   gateway (Nginx :8085)  │
                         └──┬───┬───┬───┬────────┬──┘
             ┌──────────────┘   │   │   │        └──────────────┐
   ┌─────────▼────────┐ ┌───────▼─┐ ┌▼──────────┐ ┌────────────▼──────┐
   │ iam        :1100 │ │ agent   │ │token-usage│ │ billing    :1104  │
   │ auth / JWT / SSO │ │  :1102  │ │   :1103   │ │ Stripe (test mode)│
   └──────────────────┘ │LangGraph│ └───────────┘ └───────────────────┘
                        └────┬────┘
                             │ HTTP (JWT-forwarded)
                   ┌─────────▼──────────────────────────┐
                   │  video-service :1101  + RQ worker  │  GPU box
                   │  index · search · ground · when ·  │
                   │  qa · highlights · moderate · edit │
                   └──┬──────────┬──────────┬───────────┘
                      │          │          │
              ┌───────▼──┐ ┌─────▼────┐ ┌───▼──────┐ ┌──────────┐
              │ Postgres │ │  Qdrant  │ │ MinIO/S3 │ │  Redis   │
              │ metadata │ │ vectors  │ │  media   │ │ RQ queue │
              │ timeline │ │ 10 colls │ │ features │ │          │
              │ KG       │ │          │ │ thumbs   │ │          │
              └──────────┘ └──────────┘ └──────────┘ └──────────┘
```

### Services

| Port | Service | Owns |
| --- | --- | --- |
| 8085\* | **gateway** | Nginx; routes `/api/v1/*` to internal services |
| 1100 | **iam** | register, login, Google OAuth, JWT renew, `/users/me`, admin user mgmt |
| 1101 | **video-service** (+ **video-worker**) | upload, async indexing, search, ground, when, qa, highlights, moderate, edit |
| 1102 | **agent-service** | LangGraph orchestration, SSE chat, conversation persistence, eval harness |
| 1103 | **token-usage** | LLM token logging + per-user usage stats |
| 1104 | **billing** | Stripe (test mode) subscriptions + webhooks |
| 9000 / 9001 | **minio** | S3-compatible object store + console |

\*Override with `GATEWAY_PORT` in `.env`. Postgres, Redis and Qdrant publish on
**non-default** host ports (`15432` / `16379` / `16333`) so they coexist with
other stacks on the host. Shared code (auth, DB session, RQ helpers, schemas)
lives in [`backend/cm_shared/`](backend/cm_shared/); all heavy Python deps ship
in one local base image, `jockey-base:dev` ([`backend/base_image/`](backend/base_image/)).

### The indexing pipeline (video-service)

Upload → `Video` row → `index_video` enqueued on Redis → **RQ fork-per-job worker**
(a fresh work-horse per job cold-loads ~14 GB of weights for fault isolation).
`ffprobe` routes each file to a **visual** or **audio-only** branch, cuts it into
a scene-snapped ~30 s segment grid, then fans each segment out to encoders
(each degrades gracefully if a model is missing):

- **Visual** — CLIP-L (search), DINOv2 (instance/logo), ViCLIP (motion),
  Qwen3-VL captions + visual-entities + timestamped actions, image-tile/region
  crops (small-object & logo recall)
- **Audio** — Whisper/WhisperX ASR, PANN CNN14 tags, CLAP event embeddings,
  pyannote speaker diarization
- **Text** — EasyOCR on-screen text; `text-embedding-3-large` over caption + ASR + OCR
- **Moderation** — NSFW frame score + toxic/violence text score
- **Grounding features** — InternVideo2 `[n_clips, 512]` cached to S3 (the bridge
  reused by `/ground`, `/highlights`, and the `/when` grounding-refine stream)

Then: hierarchical LLM summarization → Qdrant upsert into ~10 collections
(`jockey_shots`, `jockey_dino`, `jockey_regions`, `jockey_motion`,
`jockey_visual_entities`, `jockey_segments_text`, `jockey_audio_events`,
`jockey_timeline_events`, `jockey_videos`, `jockey_entities`) → standing timeline
(7 generators) → optional knowledge-graph extraction → thumbnails.

See [`docs/video-service-pipeline.md`](docs/video-service-pipeline.md) for the
full reference architecture.

### The agent (agent-service)

A **LangGraph** graph — `router → tool_executor → router` (looped, bounded) → `reflect → END`
— with durable per-conversation state via the **Postgres checkpointer**. It
exposes ~18 tools that call the video-service, including `search_corpus`,
`search_corpus_text`, `search_motion`, `ask_video_local`, `ground_video`,
`get_highlights`, `find_sequence`, `find_similar`, `combine_clips`,
`moderate_video`, `find_sounds`, the knowledge-graph tools
(`find_index_concepts` / `find_concept_mentions` / `find_concept_relations`),
and image tools (`search_scene_by_image`). LLMs are provider-agnostic
(**OpenAI** / **Azure** / **OpenRouter**): `gpt-4o` for routing, `gpt-4o-mini`
for reflection by default. Chat streams to the frontend over SSE.

### The frontend

**React 19 + Vite 6 + TypeScript + Tailwind v4 + Radix**, i18n in English &
Vietnamese, deployed to **Cloudflare Pages**. Main areas:

- **Workspace / Chat** (`/workspace`, `/chat/:id`) — the conversational agent
- **Console** (`/overview`, `/indexes`, `/assets`, `/entities`) — index &
  knowledge-graph management
- **Playground** (`/playground/{search,analyze,ground,segment,highlights,recommend,moderate,sounds}`)
  — one page per capability
- **Settings** (`/settings/{billing,usage,api-keys,organization,profile,...}`)
- **Admin** (`/admin/{users,billing,evaluation}`) — role-gated
- **Marketing** (`/`, `/pricing`, `/solutions`, `/product/*`) — public landing

---

## Quickstart (local, Docker Compose)

### Prerequisites

- Docker 24+ with Compose v2
- An [OpenAI](https://platform.openai.com/) key (or Azure OpenAI) for the agent LLMs
- An [OpenRouter](https://openrouter.ai/keys) key for Qwen3-VL (qa / captions) and text embeddings
- A Hugging Face token (`HF_TOKEN`) — helps model download throughput; required for gated models (pyannote)
- A CUDA GPU is strongly recommended for `video-service` indexing; the rest of the stack is CPU-fine
- Optional: Lighthouse fallback checkpoints via
  `bash backend/video-service/scripts/download_lighthouse_weights.sh ./backend/.models/lighthouse`

### Run it

```bash
git clone https://github.com/HaiVD16/tl-jockey.git
cd tl-jockey/backend

cp .env.example .env
# Fill in at least: OPENAI_API_KEY (or AZURE_OPENAI_*), OPENROUTER_API_KEY, HF_TOKEN

make base-build            # one-time: builds jockey-base:dev locally (~5-10 min, heavy)
docker compose build       # ~30s: only service code layers on top of the base
docker compose up          # everything starts in dependency order via healthchecks
```

API is live at `http://localhost:8085/api/v1/health` (or your `GATEWAY_PORT`).
After the first `make base-build`, the steady-state loop is just the last two
commands — rebuild the base only when `base_image/{Dockerfile,requirements.txt,build-constraints.txt}`
changes.

Frontend:

```bash
cd ../frontend
npm install
npm run dev                # http://localhost:5173
```

### Dev loop (hot reload)

```bash
make local-up              # stacks docker-compose.local.yml: mounts source, uvicorn --reload
```

Edits to any service's `*.py` apply in ~1s without a rebuild.

### GPU mode

```bash
LIGHTHOUSE_DEVICE=cuda make gpu-up
```

---

## Configuration

Environment lives in `backend/.env` (see [`backend/vast.env.example`](backend/vast.env.example)
and `.env.example`). Key groups:

- **Auth** — `SECRET_KEY`, `JWT_ALGORITHM`, `ACCESS_TOKEN_TTL_MIN`, `REFRESH_TOKEN_TTL_DAYS`, `GOOGLE_CLIENT_ID`
- **LLM** — `LLM_PROVIDER` (`OPENAI` | `AZURE` | `OPENROUTER`), `OPENAI_API_KEY`, `OPENAI_PLANNER_MODEL`, `OPENAI_WORKER_MODEL`, `AZURE_OPENAI_*`, `OPENROUTER_API_KEY`
- **Media / vectors** — `QDRANT_HOST/PORT/COLLECTION`, `MINIO_*`, `HF_API_KEY`
- **Infra** — `POSTGRES_*`, `REDIS_*`
- **Service URLs** — `VIDEO_SERVICE_BASE_URL`, `AGENT_SERVICE_BASE_URL`, `IAM_BASE_URL`, `TOKEN_USAGE_BASE_URL`
- **Billing** — `STRIPE_SECRET_KEY`, `STRIPE_PUBLIC_KEY` (test mode)
- **Agent stirrups** — `STIRRUP_SEARCH` / `STIRRUP_TEXTGEN` (`local` | `twelvelabs`)

---

## Deployment

Production runs a **split deployment**:

- **App tier** (gateway, iam, agent, token-usage, billing + Postgres/Redis/Qdrant/MinIO)
  on **AWS Lightsail** — `docker-compose.lightsail.yml`, reachable at `api.voiceassistant.uk`.
- **GPU tier** (`video-service` + `video-worker`) on a rented **Vast.ai GPU pod** —
  `docker-compose.vast.yml`, reached from the gateway over a Cloudflare tunnel at
  `video.voiceassistant.uk`. See [`docs/VAST_DEPLOY.md`](docs/VAST_DEPLOY.md).
- **Frontend** on **Cloudflare Pages** — `app.voiceassistant.uk`.

Long-running indexing is dispatched to the `video_index` Redis queue and drained
by the RQ `video-worker` (scale with `docker compose up -d --scale video-worker=N`;
CUDA MPS lets replicas share one GPU).

---

## Repository layout

```
backend/
  gateway/         Nginx reverse proxy (api_gateway.conf.template)
  iam/             auth + users + admin
  video-service/   indexing pipeline, encoders, search/ground/when/qa APIs, RQ worker
  agent-service/   LangGraph agent, tools, SSE chat, eval harness
  token-usage/     LLM usage logging
  billing/         Stripe (test mode) subscriptions
  cm_shared/       shared auth / db / queue / schemas
  base_image/      jockey-base:dev (all heavy deps)
  database/        Postgres/Redis/Qdrant/MinIO compose
  docker-compose*.yml   local / gpu / vast / lightsail variants
frontend/          React 19 + Vite + Tailwind SPA (Cloudflare Pages)
jockey/            legacy standalone LangGraph agent (project origin)
vendor/sg-detr/    SG-DETR / MRDETR grounding model
docs/              pipeline, use-case coverage, deploy, diagrams, thesis
video/             sample videos (basketball, cooking, tennis, nature, …)
```

## Documentation

- [`docs/video-service-pipeline.md`](docs/video-service-pipeline.md) — offline indexing + online propose reference architecture
- [`docs/USE_CASE_COVERAGE.md`](docs/USE_CASE_COVERAGE.md) — capability audit vs Twelve Labs Playground use cases
- [`docs/VAST_DEPLOY.md`](docs/VAST_DEPLOY.md) — GPU-pod deployment
- [`docs/diagrams/`](docs/diagrams/) — per-module architecture diagrams
- [`backend/README.md`](backend/README.md) · [`frontend/README.md`](frontend/README.md) · [`backend/billing/README.md`](backend/billing/README.md)

---

## Contributors

Contribution by Cody254, CaptCherry1710
