# Vast.ai 4090 deployment

`video-service` + `video-worker` run on the rented box; everything else stays
on the laptop. Joined by Tailscale (`jockey-mac` + `jockey-vast`). No new
abstractions — same FastAPI app, same containers, just different hostnames
in the gateway and `.env`.

## Architecture

```
[laptop — your existing docker compose minus video-service/worker]
  frontend (vite) — gateway — iam — agent-service — token-usage
  postgres — redis — qdrant — minio
                                       ▲                  │
                                       │ tailnet          │ /index, /search, /segment
                                       │                  ▼
[vast.ai 4090 — manual rent per demo session]
  video-service + video-worker (Dockerfile.gpu)
  /models on a Vast host-disk volume (survives destroy+recreate)
```

## One-time setup

### On the laptop

1. Install Tailscale, sign in, set the hostname:
   ```bash
   tailscale up --hostname=jockey-mac
   tailscale status         # confirm 100.x.y.z address
   ```
2. Make sure Postgres / Redis / Qdrant / MinIO are reachable on the tailnet —
   they're already bound to host ports (`15432`, `16379`, `9000`, `6333`) so
   Tailscale forwards them transparently. No firewall changes needed.

### On the vast.ai instance (first time)

1. **Rent the box.** Pick a 4090 24 GB, on-demand (not interruptible), PyTorch
   image, **≥80 GB disk**, **host-disk volume for `/workspace/models`** (so
   pyannote/Paddle/InsightFace weights survive instance destroy+recreate).
2. **Join the tailnet.** Generate a [reusable auth key](https://login.tailscale.com/admin/settings/keys),
   then on the box:
   ```bash
   curl -fsSL https://tailscale.com/install.sh | sh
   sudo tailscale up --authkey=tskey-... --hostname=jockey-vast --ssh
   tailscale status
   ```
3. **Clone the repo.**
   ```bash
   git clone https://github.com/<you>/tl-jockey.git
   cd tl-jockey/backend
   cp .env.example .env
   ```
4. **Edit `.env` on the box.** Override these:
   ```
   POSTGRES_HOST=jockey-mac
   REDIS_HOST=jockey-mac
   QDRANT_HOST=jockey-mac
   MINIO_ENDPOINT=http://jockey-mac:9000
   IAM_BASE_URL=http://jockey-mac:1100
   AGENT_SERVICE_BASE_URL=http://jockey-mac:1102
   TOKEN_USAGE_BASE_URL=http://jockey-mac:1103
   HF_TOKEN=hf_...        # required for pyannote
   VAST_MODELS_PATH=/workspace/models
   ```
5. **Build + bring up just video-service + worker.**
   ```bash
   # For Ampere / Ada / Hopper (RTX 3090 / 4090, A100, H100):
   docker compose -f docker-compose.vast.yml build
   #
   # For Blackwell (RTX 5070 Ti / 5080 / 5090) — needs cu124+ PyTorch:
   docker compose -f docker-compose.vast.yml build \
       --build-arg BASE_IMAGE=pytorch/pytorch:2.6.0-cuda12.4-cudnn9-runtime

   docker compose -f docker-compose.vast.yml up -d
   docker compose -f docker-compose.vast.yml logs -f video-service
   ```
   First boot pulls pyannote (~1.5 GB), PaddleOCR (~600 MB), InsightFace
   (~500 MB), Whisper distil-large-v3 (~750 MB CT2-quantized) into `/models`.
   Subsequent boots are seconds.

   **Sanity-check the GPU is usable** before running a real workload:
   ```bash
   docker compose -f docker-compose.vast.yml exec video-service \
       python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
   # → True NVIDIA GeForce RTX 5070 Ti
   ```
   If you see `False`, or `no kernel image available` on first inference, the
   PyTorch build doesn't target this GPU's compute capability — rebuild with
   the `BASE_IMAGE` override above.

### Local-side flip

After the box is up and `ping jockey-vast` works from the laptop:

```bash
# Look up the tailnet IPv4 of the box (MagicDNS hostnames don't resolve from
# the gateway's bridge network, so we pin to the IP).
tailscale ip -4 jockey-vast
# → 100.x.y.z

# Edit backend/.env
echo "VIDEO_UPSTREAM=100.x.y.z:1101" >> backend/.env

# Restart only the gateway — it picks up VIDEO_UPSTREAM via envsubst on
# /etc/nginx/templates/api_gateway.conf.template at container start.
docker compose -f backend/docker-compose.yml -f backend/docker-compose.local.yml restart gateway

# Sanity: the frontend's video-service calls should now land on the GPU box.
curl -s http://localhost:8085/api/v1/videos -H "Authorization: Bearer $TOKEN" | head
```

## Per-session bring-up

```bash
# On the vast box (if you destroyed the instance and re-rented)
docker compose -f docker-compose.vast.yml up -d

# On the laptop
docker compose -f backend/docker-compose.yml -f backend/docker-compose.local.yml restart gateway
```

## Per-session tear-down

When you're done demoing, **stop the vast instance** so you don't pay for idle
GPU time:

```bash
# On the vast box
docker compose -f docker-compose.vast.yml down

# Optionally destroy the whole instance — /models persists on the host-disk
# volume and re-attaches when you re-rent.
```

The frontend's `/api/v1/videos` calls will 502 through the gateway until you
bring the box back up. That's expected — Segment is a demo feature, not an
always-on product.

## What `docker-compose.vast.yml` does

- Builds `Dockerfile.gpu` (CUDA runtime + pyannote + PaddleOCR + InsightFace
  on top of the local base image).
- Reserves one NVIDIA GPU per service.
- Mounts `${VAST_MODELS_PATH}` → `/models` (host-disk volume, persistent).
- Uses `network_mode: host` so `100.x.y.z:1101` and the tailnet routes work
  without bridge translation.
- Env-driven hostnames default to `jockey-mac`, override in `.env` if your
  Tailscale hostnames are different.

## Bandwidth note

Indexing a video does upload-to-MinIO (laptop LAN) → vast worker downloads
over Tailscale → process on GPU → write embeddings back to local Qdrant.
For a 200 MB video on a typical 50 Mbps home upload, that's ~30 s of pure
transfer per video before any compute. Fine for thesis-scale demos. For bulk
indexing 1000+ videos, run the indexer **on the box** with videos uploaded
straight to a vast-side scratch bucket (skip MinIO round-trip).

## Cost guard

- 4090 on-demand: ~$0.35-0.45/hr on vast.ai bidding.
- Typical demo session: 2-4 hours.
- Monthly: $5-15 if you're disciplined about `docker compose down` + instance
  stop between sessions. **Don't leave it running overnight.**
