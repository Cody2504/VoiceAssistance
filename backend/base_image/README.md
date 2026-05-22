# jockey-base

Shared base image for all tl-jockey backend services. Mirrors the pattern in
`/home/hai/project/ai-backend/base_image`.

## Build

```bash
make base-build               # tags jockey-base:dev locally
# or
docker build -t jockey-base:dev ./backend/base_image
```

The base image only needs to rebuild when:

- `requirements.txt` changes
- `build-constraints.txt` changes
- `Dockerfile` itself changes
- Apt deps in the builder/runtime stages change

Per-service Dockerfiles `FROM jockey-base:dev` and only `COPY` source code, so
editing service Python files rebuilds in seconds.

## What's inside

- Python 3.11
- `/opt/venv` virtualenv (on `$PATH`) containing every Python dep from
  `requirements.txt`, plus `torch==2.4.1 torchvision==0.19.1` from the
  PyTorch CPU index.
- Runtime apt libs: `ffmpeg`, `libsndfile1`, `libpq5`, `libgl1`, `libglib2.0-0`.

## Build mechanics that matter for speed

1. **Multi-stage**: compilers stay in the builder; runtime image ships a
   trimmed venv only.
2. **uv** (instead of pip): parallel resolver + downloader, typically 5-10×
   faster on a cold install.
3. **BuildKit cache mount** (`--mount=type=cache,target=/root/.cache/uv`):
   wheels stay on the host between rebuilds and even across `docker builder
   prune`, so changing requirements.txt re-uses cached wheels.
4. **Torch from CPU index**: pulls a ~150 MB CPU wheel instead of ~700 MB of
   nvidia-cu12-* dependencies.
5. **Venv stripping**: removes `include/`, `__pycache__/`, and `*.a` files
   before the runtime stage copies the venv across.
