#!/usr/bin/env bash
# vast-bootstrap.sh — install + run video-service and the RQ worker on a
# vast.ai pod (which is itself a Docker container, so we do NOT run docker
# again here — just install Python deps directly and start uvicorn + the
# RQ worker in tmux sessions).
#
# Usage:
#   bash backend/scripts/vast-bootstrap.sh install         # uv pip install + weights
#   bash backend/scripts/vast-bootstrap.sh start           # boot api + N workers
#   bash backend/scripts/vast-bootstrap.sh stop            # kill tmux sessions
#   bash backend/scripts/vast-bootstrap.sh restart         # stop && start
#   bash backend/scripts/vast-bootstrap.sh status          # ps + tmux list + GPU
#   bash backend/scripts/vast-bootstrap.sh logs api        # attach api session
#   bash backend/scripts/vast-bootstrap.sh logs worker     # attach worker #1
#   bash backend/scripts/vast-bootstrap.sh logs worker 2   # attach worker #2
#   bash backend/scripts/vast-bootstrap.sh all             # install + start (default)
#
# Conventions:
#   - Repo lives at $REPO_DIR (default /workspace/VoiceAssistance).
#   - Env file at $REPO_DIR/backend/vast.env (template: vast.env.example).
#   - Lighthouse weights at $MODELS_DIR/lighthouse/ (default /workspace/models/lighthouse).
#   - tmux sessions: "vs-api" (uvicorn), "vs-worker-1", "vs-worker-2", ...
#     (count from $WORKER_COUNT, default 2 — sized for a 24 GB RTX 3090).
#
# This script is intentionally idempotent — running `install` twice is safe.
#
# Recommended vast.ai image:
#   pytorch/pytorch:2.4.1-cuda12.4-cudnn9-runtime
# Compatible with RTX 3090 / 4090 / A100 / H100. For RTX 50-series (Blackwell)
# use 2.6.0-cuda12.4-cudnn9-runtime instead; everything else stays the same.

set -euo pipefail

# ----------------------------------------------------------- paths & config
REPO_DIR="${REPO_DIR:-/workspace/VoiceAssistance}"
BACKEND_DIR="${REPO_DIR}/backend"
SERVICE_DIR="${BACKEND_DIR}/video-service"
SHARED_DIR="${BACKEND_DIR}/cm_shared"
ENV_FILE="${VAST_ENV_FILE:-${BACKEND_DIR}/vast.env}"
MODELS_DIR="${MODELS_DIR:-/workspace/models}"
LIGHTHOUSE_DIR="${MODELS_DIR}/lighthouse"

API_SESSION="vs-api"
WORKER_SESSION_PREFIX="vs-worker"     # actual sessions: vs-worker-1, vs-worker-2, ...
API_PORT="${API_PORT:-1101}"

# Number of RQ worker processes to run in parallel. Each loads its own copy
# of the heavy models (Lighthouse + ViCLIP + Whisper + PANN + ...) into VRAM.
# On an RTX 3090 (24 GB) two workers fit comfortably (≈ 8 GB each at idle,
# plus activations); 3 is the practical ceiling. Override in vast.env.
WORKER_COUNT="${WORKER_COUNT:-2}"

# Torch / CUDA target. The vast pytorch:2.4.1-cuda12.4-cudnn9-runtime image
# is the canonical stable base for RTX 3090 / 4090 / A100. On generic
# (non-pytorch) vast images the preflight will install this exact pinned set
# automatically from the cu124 wheel index — driver back-compat means cu124
# works on any host driver ≥ 545 (so RTX 3090 / 4090 / A100 / H100, and also
# RTX 5090 with the 2.6.0 override).
TORCH_MIN_VERSION="${TORCH_MIN_VERSION:-2.4}"
TORCH_VERSION="${TORCH_VERSION:-2.4.1}"
TORCHVISION_VERSION="${TORCHVISION_VERSION:-0.19.1}"
TORCHAUDIO_VERSION="${TORCHAUDIO_VERSION:-2.4.1}"
TORCH_INDEX_URL="${TORCH_INDEX_URL:-https://download.pytorch.org/whl/cu124}"
# For Ubuntu 24.04 generic image where system Python is PEP-668 marked.
# Harmless on pytorch-base images.
PIP_BREAK="${PIP_BREAK:---break-system-packages}"

# Python interpreter to use for `python -m uvicorn` / RQ worker invocations.
# Auto-detected at runtime by detect_py(): on vast.ai's stock image torch +
# uvicorn end up in /venv/main, not in /usr/bin/python3. Override by setting
# PY_BIN explicitly (e.g. PY_BIN=/opt/conda/bin/python on pytorch-base images).
PY_BIN="${PY_BIN:-}"

# ------------------------------------------------------------------- colors
RED=$'\e[31m'; GRN=$'\e[32m'; YLW=$'\e[33m'; BLU=$'\e[34m'; NC=$'\e[0m'
info() { printf "%s[*]%s %s\n" "$BLU" "$NC" "$*"; }
ok()   { printf "%s[OK]%s %s\n" "$GRN" "$NC" "$*"; }
warn() { printf "%s[!!]%s %s\n" "$YLW" "$NC" "$*"; }
die()  { printf "%s[ERR]%s %s\n" "$RED" "$NC" "$*" >&2; exit 1; }

# ------------------------------------------------------------ env loader
load_env() {
  if [[ -f "$ENV_FILE" ]]; then
    info "loading env from $ENV_FILE"
    # `set -a` exports every variable assigned in the sourced file.
    set -a
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +a
  else
    warn "no env file at $ENV_FILE — relying on already-exported variables"
    warn "copy backend/vast.env.example to backend/vast.env and fill it in"
  fi

  # Strip stray CRLF endings from vast.env in place — values with a trailing
  # \r silently break things downstream (e.g. SECRET_KEY+\r ≠ SECRET_KEY,
  # so JWT signature verification fails despite "matching" secrets).
  # Origin: pasting / heredoc'ing the file through Windows-side tools or
  # SSH-with-TTY which injects CR.
  if [[ -f "$ENV_FILE" ]] && grep -q $'\r' "$ENV_FILE" 2>/dev/null; then
    info "stripping CRLF from $ENV_FILE"
    sed -i 's/\r$//' "$ENV_FILE"
    # re-source so the cleaned values land in the current shell's env
    set -a; source "$ENV_FILE"; set +a
  fi

  # PYTHONPATH must include backend/ so that `import cm_shared.*` resolves.
  # The bootstrap `cd`s into SERVICE_DIR before uvicorn / RQ workers, so the
  # `main.` package works from cwd — we only need BACKEND_DIR added here.
  # Set unconditionally (vast.env doesn't list it) and idempotently (don't
  # double-add on re-runs). Was migration-log #12 ("PYTHONPATH not effective
  # despite being set" — accidentally fixed via whitespace-stripping then
  # silently re-broken).
  case ":${PYTHONPATH:-}:" in
    *":${BACKEND_DIR}:"*) ;;
    *) export PYTHONPATH="${BACKEND_DIR}${PYTHONPATH:+:${PYTHONPATH}}" ;;
  esac
  info "PYTHONPATH=${PYTHONPATH}"
}

# ------------------------------------------------------------ ensure tools
ensure_uv() {
  if command -v uv >/dev/null 2>&1; then
    return
  fi
  info "installing uv (astral) into ~/.local/bin"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
  command -v uv >/dev/null 2>&1 || die "uv install failed — see https://docs.astral.sh/uv/"
}

ensure_system_packages() {
  # The vast pytorch:cuda images ship with apt; ffmpeg is required for
  # decord / lighthouse / ASR audio extraction.
  if ! command -v ffmpeg >/dev/null 2>&1; then
    info "installing system packages (ffmpeg, libsndfile, tmux)"
    apt-get update -qq
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      ffmpeg libsndfile1 tmux curl ca-certificates
  fi
  command -v tmux >/dev/null 2>&1 || \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends tmux
}

# ------------------------------------------------------------ install deps
_pip_install_torch_stack() {
  # Install the canonical cu124 torch trio. Used both when torch is missing
  # entirely (generic vast image) and when torchaudio is the only thing
  # missing (some pytorch-base images ship torch+torchvision but not audio).
  info "installing torch==${TORCH_VERSION} torchvision==${TORCHVISION_VERSION} torchaudio==${TORCHAUDIO_VERSION} from ${TORCH_INDEX_URL}"
  pip install ${PIP_BREAK} --index-url "${TORCH_INDEX_URL}" \
    "torch==${TORCH_VERSION}" \
    "torchvision==${TORCHVISION_VERSION}" \
    "torchaudio==${TORCHAUDIO_VERSION}" \
    || die "torch stack install failed — check ${TORCH_INDEX_URL} has cp$(python3 -c 'import sys;print(sys.version_info.major,sys.version_info.minor,sep=\"\")') wheels"
}

preflight_torch() {
  # On a pytorch-base image, torch + torchvision + (sometimes) torchaudio
  # are already present and CUDA-visible. On a generic image, install the
  # pinned stack from the cu124 wheel index. Versions are pinned at the top
  # of this script (TORCH_VERSION / TORCHVISION_VERSION / TORCHAUDIO_VERSION)
  # so future pods don't drift.
  info "preflight: checking torch + CUDA"
  if ! python3 -c "import torch" 2>/dev/null; then
    info "torch missing — installing pinned cu124 stack"
    _pip_install_torch_stack
  fi
  python3 - <<EOF || die "torch preflight failed — see above"
import sys, torch
v = torch.__version__
cuda = getattr(torch.version, "cuda", None)
print(f"  torch={v}  cuda={cuda}  device_count={torch.cuda.device_count()}")
if not torch.cuda.is_available():
    print("ERROR: torch installed but CUDA not visible. nvidia-smi?", file=sys.stderr)
    sys.exit(2)
maj, min_ = [int(x) for x in v.split('+')[0].split('.')[:2]]
tmaj, tmin = [int(x) for x in "${TORCH_MIN_VERSION}".split('.')]
if (maj, min_) < (tmaj, tmin):
    print(f"ERROR: torch {v} < required {tmaj}.{tmin}", file=sys.stderr)
    sys.exit(3)
# CUDA version sanity — warn if not 12.x family (we standardize on cu124).
if cuda and not cuda.startswith("12."):
    print(f"WARNING: torch was built against CUDA {cuda}, expected 12.x", file=sys.stderr)
EOF
  # torchvision + torchaudio — install if missing. On a pytorch-base image
  # that already has torch, this only fills in torchaudio (or both, if the
  # image is torch-only).
  for mod in torchvision torchaudio; do
    if ! python3 -c "import ${mod}" 2>/dev/null; then
      info "${mod} missing — installing matching cu124 stack"
      _pip_install_torch_stack
      break
    fi
  done
  ok "torch preflight passed"
}


install_deps() {
  ensure_system_packages
  ensure_uv
  preflight_torch

  info "installing core Python deps via uv (system Python, no venv)"
  # --system: install into the pod's system Python. The vast pytorch pod
  # ships with torch+CUDA already in place; building a venv would re-pull
  # several GB.
  uv pip install --system \
    -r "${SHARED_DIR}/requirements.txt" \
    -r "${SERVICE_DIR}/requirements.txt"

  # msclap with --no-deps: its 1.3.x line pins torchvision>=0.16,<0.17 which
  # has no cp312 wheels (max cp311). The pod is Python 3.12; we already
  # installed modern torch + torchvision via the preflight. msclap only uses
  # basic torchvision preprocessing and is API-compatible up to 0.20+.
  info "installing msclap (--no-deps; reuses already-installed torchvision)"
  uv pip install --system --no-deps "msclap==1.3.3"

  # Lighthouse last, with --no-deps. Its setup.py pins `numpy<=1.23.5`,
  # which collides with everything else we depend on (transformers, decord,
  # scenedetect, ...). All of Lighthouse's real runtime deps are pinned in
  # requirements.txt above at versions that actually work.
  #
  # NB: install as `lighthouse` (the name in setup.py), not `lighthouse-mr` —
  # uv enforces name match with the wheel/sdist metadata, pip does not.
  info "installing lighthouse (--no-deps; runtime deps installed above)"
  uv pip install --system --no-deps \
    "lighthouse @ git+https://github.com/line/lighthouse.git@main"

  # Optional segmenters — only install if INSTALL_SEGMENTERS=1 in vast.env.
  # These are 1-2 GB combined and only needed for tiles that aren't part of
  # the core MR/HD/Q&A flow:
  #   - pyannote.audio  → speaker_diarization segmenter (needs HF_TOKEN +
  #                        the user has accepted the pyannote license)
  #   - paddleocr       → on-screen text segmenter
  #   - insightface     → person_of_focus segmenter
  if [[ "${INSTALL_SEGMENTERS:-0}" == "1" ]]; then
    info "installing optional segmenter deps (INSTALL_SEGMENTERS=1)"
    uv pip install --system \
      "pyannote.audio>=3.1,<4.0" \
      "paddleocr>=2.7" \
      "insightface>=0.7" \
      "onnxruntime-gpu>=1.17" \
      "opencv-python-headless>=4.9" \
      "paddlepaddle-gpu>=2.6"
  else
    info "skipping optional segmenters — set INSTALL_SEGMENTERS=1 to enable"
  fi

  ok "Python deps installed"
}

# ------------------------------------------------------------ lighthouse weights
download_weights() {
  if [[ -f "${LIGHTHOUSE_DIR}/clip_slowfast_cg_detr_qvhighlight.ckpt" ]] \
     && [[ -f "${LIGHTHOUSE_DIR}/clap_qd_detr_clotho_moment.ckpt" ]]; then
    ok "lighthouse weights already present at ${LIGHTHOUSE_DIR}"
    return
  fi
  info "downloading Lighthouse weights to ${LIGHTHOUSE_DIR}"
  bash "${SERVICE_DIR}/scripts/download_lighthouse_weights.sh" "${LIGHTHOUSE_DIR}"
  ok "Lighthouse weights ready"
}

# ------------------------------------------------------------ db migration
run_migrations() {
  detect_py
  info "running alembic migrations against ${POSTGRES_HOST:-?}:${POSTGRES_PORT:-?}"
  # `python -m alembic` instead of bare `alembic` so we use the same
  # interpreter that has the deps installed (PY_BIN, not the random one on PATH).
  ( cd "${SERVICE_DIR}" \
    && PYTHONPATH="${BACKEND_DIR}${PYTHONPATH:+:${PYTHONPATH}}" \
       "${PY_BIN}" -m alembic upgrade head ) || \
    warn "alembic upgrade failed — check POSTGRES_HOST/PORT/USER/PASSWORD/DB and that cm_shared is importable"
}

# ------------------------------------------------------------ start / stop
session_exists() {
  tmux has-session -t "$1" 2>/dev/null
}

# Resolve the Python interpreter that actually has uvicorn / torch / etc.
# Scans the well-known venv locations on vast.ai images, falls back to PATH.
# Called by run_migrations / start_api / start_workers — these run from a
# tmux `bash -lc` that doesn't auto-activate venvs, so we have to hand it
# the full binary path.
detect_py() {
  if [[ -n "$PY_BIN" ]] && [[ -x "$PY_BIN" ]]; then
    return
  fi
  for cand in /venv/main/bin/python3 /opt/conda/bin/python /opt/conda/bin/python3 \
              "$(command -v python3 2>/dev/null)"; do
    if [[ -x "$cand" ]] && "$cand" -c "import uvicorn" 2>/dev/null; then
      PY_BIN="$cand"
      info "detected PY_BIN=${PY_BIN}"
      return
    fi
  done
  die "no python interpreter found with uvicorn installed — set PY_BIN explicitly"
}

# Enumerate the worker tmux session names for the configured WORKER_COUNT.
worker_sessions() {
  local i
  for ((i = 1; i <= WORKER_COUNT; i++)); do
    echo "${WORKER_SESSION_PREFIX}-${i}"
  done
}

start_api() {
  if session_exists "$API_SESSION"; then
    warn "tmux session '$API_SESSION' already running — skip"
    return
  fi
  detect_py
  info "starting uvicorn (api) in tmux session '$API_SESSION' on :${API_PORT}"
  # tmux's bash -lc only sources login rc files; if the pod uses an auto-
  # activated venv (e.g. vast.ai's /venv/main) that the rc files don't pick
  # up, `uvicorn` (and the venv's python) won't be on PATH. Invoke the
  # interpreter PY_BIN by absolute path — detect_py picked one that has
  # uvicorn installed.
  tmux new -d -s "$API_SESSION" \
    "bash -lc 'cd ${SERVICE_DIR} && \
       set -a; source ${ENV_FILE} 2>/dev/null || true; set +a; \
       export PYTHONPATH=${BACKEND_DIR}\${PYTHONPATH:+:\$PYTHONPATH}; \
       exec ${PY_BIN} -m uvicorn main.main:app --host 0.0.0.0 --port ${API_PORT}'"
  ok "api session started — attach with: tmux attach -t $API_SESSION"
}

start_workers() {
  # Spawn WORKER_COUNT independent RQ worker processes, each in its own tmux
  # session. They all listen on the same Redis queue (video_index) — RQ
  # itself distributes jobs across them. Per-worker model load happens lazily
  # at first job (Lighthouse, ViCLIP, Whisper, etc.), so initial idle VRAM
  # is small; steady-state VRAM ≈ WORKER_COUNT × ~8 GB on a 3090 with two
  # workers active.
  detect_py
  info "starting ${WORKER_COUNT} RQ worker(s)"
  local idx
  for ((idx = 1; idx <= WORKER_COUNT; idx++)); do
    local name="${WORKER_SESSION_PREFIX}-${idx}"
    if session_exists "$name"; then
      warn "  $name already running — skip"
      continue
    fi
    tmux new -d -s "$name" \
      "bash -lc 'cd ${SERVICE_DIR} && \
         set -a; source ${ENV_FILE} 2>/dev/null || true; set +a; \
         export PYTHONPATH=${BACKEND_DIR}\${PYTHONPATH:+:\$PYTHONPATH}; \
         export RQ_WORKER_ID=${idx}; \
         exec ${PY_BIN} -m main.workers.queue_worker'"
    ok "  $name started"
  done
}

stop_session() {
  local name="$1"
  if session_exists "$name"; then
    info "stopping tmux session '$name'"
    tmux kill-session -t "$name"
  else
    warn "no tmux session '$name' to stop"
  fi
}

stop_workers() {
  # Stop every session matching the worker prefix — handles the case where
  # the user reduced WORKER_COUNT between runs and we have stragglers.
  local s
  for s in $(tmux list-sessions -F '#S' 2>/dev/null | grep -E "^${WORKER_SESSION_PREFIX}(-[0-9]+)?$" || true); do
    stop_session "$s"
  done
}

# ------------------------------------------------------------ status / logs
status() {
  echo
  info "tmux sessions (api + ${WORKER_COUNT} workers)"
  tmux list-sessions 2>/dev/null | sed 's/^/   /' || echo "   (none)"
  echo
  info "uvicorn on :${API_PORT}"
  if curl -fsS "http://127.0.0.1:${API_PORT}/health" >/dev/null 2>&1; then
    ok "  /health responds 200"
  else
    warn "  /health not responding (give it a few seconds after start)"
  fi
  echo
  info "RQ workers — Redis queue depth"
  if command -v python3 >/dev/null 2>&1; then
    python3 - 2>/dev/null <<EOF || warn "  (could not connect to redis)"
import os
from redis import Redis
r = Redis(host=os.environ.get("REDIS_HOST","127.0.0.1"),
          port=int(os.environ.get("REDIS_PORT","6379")))
print(f"   queued:   {r.llen('rq:queue:video_index')}")
print(f"   started:  {r.scard('rq:wip:video_index')}")
print(f"   workers:  {sum(1 for k in r.scan_iter('rq:worker:*'))}")
EOF
  fi
  echo
  info "GPU"
  if command -v nvidia-smi >/dev/null 2>&1; then
    nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu \
      --format=csv,noheader | sed 's/^/   /'
  else
    echo "   (no nvidia-smi)"
  fi
}

logs() {
  # `logs api`             → attach the uvicorn session
  # `logs worker`          → attach worker #1
  # `logs worker 2`        → attach worker #2
  local which="${1:-api}"
  local idx="${2:-1}"
  case "$which" in
    api)    tmux attach -t "$API_SESSION"                       ;;
    worker) tmux attach -t "${WORKER_SESSION_PREFIX}-${idx}"    ;;
    *)      die "logs: pick 'api' or 'worker [N]'"              ;;
  esac
}

# ------------------------------------------------------------ dispatch
cmd="${1:-all}"
case "$cmd" in
  install)
    load_env
    install_deps
    download_weights
    ;;
  start)
    load_env
    run_migrations
    start_api
    start_workers
    status
    ;;
  stop)
    stop_session "$API_SESSION"
    stop_workers
    ;;
  restart)
    stop_session "$API_SESSION"
    stop_workers
    load_env
    run_migrations
    start_api
    start_workers
    status
    ;;
  status)
    status
    ;;
  logs)
    logs "${2:-api}" "${3:-1}"
    ;;
  all)
    load_env
    install_deps
    download_weights
    run_migrations
    start_api
    start_workers
    status
    ;;
  *)
    die "unknown command '$cmd' — try: install | start | stop | restart | status | logs [api|worker [N]] | all"
    ;;
esac
