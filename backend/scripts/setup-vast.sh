#!/usr/bin/env bash
# setup-vast.sh — one-shot, idempotent bring-up of the vast.ai pod side:
# installs cloudflared, starts 3 `cloudflared access tcp` listeners that bring
# the laptop's pg/redis/qdrant to 127.0.0.1 on the pod, runs the inbound tunnel
# `jockey-vast` so video.voiceassistant.uk → 127.0.0.1:1101, then hands off to
# vast-bootstrap.sh to bring up uvicorn + RQ workers.
#
# Prereqs that you MUST do once on the LAPTOP before running this on the pod:
#   1. cloudflared tunnel create jockey-vast            # produces <UUID>.json
#   2. cloudflared tunnel route dns -f jockey-vast video.voiceassistant.uk
#   3. scp ~/.cloudflared/<UUID>.json root@<pod>:/root/.cloudflared/
#      (and remember the UUID — pass it as JOCKEY_VAST_UUID env var below, or
#      the script will pick the only .json in /root/.cloudflared/)
#
# Usage:
#   bash backend/scripts/setup-vast.sh                  # full bring-up
#   bash backend/scripts/setup-vast.sh env              # prompt + write vast.env
#   bash backend/scripts/setup-vast.sh listeners        # start the 3 tcp tunnels
#   bash backend/scripts/setup-vast.sh tunnel           # start jockey-vast tunnel
#   bash backend/scripts/setup-vast.sh app              # install + start api+workers
#   bash backend/scripts/setup-vast.sh stop             # kill tmux tunnels + app
#   bash backend/scripts/setup-vast.sh status

set -euo pipefail

# ----------------------------------------------------------- paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_DIR="$(cd "${BACKEND_DIR}/.." && pwd)"

ZONE="voiceassistant.uk"
TUNNEL_NAME="jockey-vast"
CF_DIR="/root/.cloudflared"
API_PORT="${API_PORT:-1101}"

# Listeners that the pod opens on 127.0.0.1 — these are what vast.env's
# POSTGRES_HOST=127.0.0.1:15432 etc. actually connect through.
# Format: <session>|<hostname>|<local-port>
LISTENERS=(
  "tun-pg|pg.${ZONE}|15432"
  "tun-redis|redis.${ZONE}|16379"
  "tun-qdrant|qdrant.${ZONE}|6333"
)

VAST_TUNNEL_SESSION="tun-video"

# ----------------------------------------------------------- pretty
RED=$'\e[31m'; GRN=$'\e[32m'; YLW=$'\e[33m'; BLU=$'\e[34m'; NC=$'\e[0m'
info() { printf "%s[*]%s %s\n" "$BLU" "$NC" "$*"; }
ok()   { printf "%s[OK]%s %s\n" "$GRN" "$NC" "$*"; }
warn() { printf "%s[!!]%s %s\n" "$YLW" "$NC" "$*"; }
die()  { printf "%s[ERR]%s %s\n" "$RED" "$NC" "$*" >&2; exit 1; }

session_exists() { tmux has-session -t "$1" 2>/dev/null; }

# ----------------------------------------------------------- env file
ensure_env() {
  local target="${BACKEND_DIR}/vast.env"
  local template="${BACKEND_DIR}/vast.env.example"

  if [[ -f "$target" ]]; then
    ok "vast.env already present at $target"
  else
    [[ -f "$template" ]] || die "missing $template — pull the repo properly"
    info "creating $target from template"
    cp "$template" "$target"
    warn "edit $target and fill at minimum: OPENROUTER_API_KEY, HF_TOKEN"
    warn "the POSTGRES/REDIS/QDRANT hosts default to 127.0.0.1 — leave them alone"
    warn "MINIO_ENDPOINT defaults to https://minio.${ZONE} — leave that alone too"
    read -rp "press Enter once you've filled the keys, or Ctrl-C to abort... "
  fi

  # MIGRATION_LOG problem #12: strip stray leading whitespace before `export`.
  sed -i 's/^[[:space:]]\+export /export /' "$target"

  # MIGRATION_LOG problem #19: rewrite stale path if it slipped through.
  sed -i "s|/workspace/jockey-repo/|/workspace/VoiceAssistance/|g" "$target"

  # Sanity-check required values.
  set -a; source "$target"; set +a
  [[ -n "${OPENROUTER_API_KEY:-}" ]] || die "OPENROUTER_API_KEY not set in vast.env"
  [[ -n "${HF_TOKEN:-}" ]] || warn "HF_TOKEN empty — pyannote will fail if you enable segmenters"
  ok "vast.env validated"
}

# ----------------------------------------------------------- system tools
ensure_tools() {
  local need=()
  command -v tmux       >/dev/null 2>&1 || need+=(tmux)
  command -v curl       >/dev/null 2>&1 || need+=(curl)
  command -v ca-certificates >/dev/null 2>&1 || need+=(ca-certificates)
  if (( ${#need[@]} > 0 )); then
    info "apt-get install: ${need[*]}"
    apt-get update -qq
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends "${need[@]}"
  fi
}

ensure_cloudflared() {
  if command -v cloudflared >/dev/null 2>&1; then
    ok "cloudflared present ($(cloudflared --version 2>&1 | head -1))"
    return
  fi
  info "downloading cloudflared static binary"
  curl -fsSL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 \
    -o /usr/local/bin/cloudflared
  chmod +x /usr/local/bin/cloudflared
  ok "cloudflared installed to /usr/local/bin/cloudflared"
}

# ----------------------------------------------------------- TCP listeners
# These give the pod 127.0.0.1:15432/16379/6333 → laptop's pg/redis/qdrant
# via Cloudflare's TCP access tunnel. No credentials needed on this side —
# the access tunnel reaches the public hostname.
start_listeners() {
  for row in "${LISTENERS[@]}"; do
    local sess host port
    IFS='|' read -r sess host port <<<"$row"
    if session_exists "$sess"; then
      ok "  $sess already running"
      continue
    fi
    info "starting access listener ${sess}: 127.0.0.1:${port} ← ${host}"
    tmux new -d -s "$sess" \
      "cloudflared access tcp --hostname ${host} --url 127.0.0.1:${port}"
    ok "  $sess started"
  done
  sleep 2
  for row in "${LISTENERS[@]}"; do
    local sess host port
    IFS='|' read -r sess host port <<<"$row"
    if (echo >/dev/tcp/127.0.0.1/${port}) 2>/dev/null; then
      ok "  127.0.0.1:${port} reachable"
    else
      warn "  127.0.0.1:${port} not reachable yet — check 'tmux a -t ${sess}'"
    fi
  done
}

# ----------------------------------------------------------- inbound tunnel
ensure_vast_credentials() {
  mkdir -p "$CF_DIR"

  if [[ -n "${JOCKEY_VAST_UUID:-}" ]]; then
    TUNNEL_UUID="$JOCKEY_VAST_UUID"
  else
    # Pick the only .json present, or bail.
    local found
    mapfile -t found < <(find "$CF_DIR" -maxdepth 1 -name '*.json' -printf '%f\n')
    if (( ${#found[@]} == 0 )); then
      die "no credentials JSON in ${CF_DIR}. On laptop:
   cloudflared tunnel create ${TUNNEL_NAME}
   cloudflared tunnel route dns -f ${TUNNEL_NAME} video.${ZONE}
   scp ~/.cloudflared/<UUID>.json root@<pod>:${CF_DIR}/"
    elif (( ${#found[@]} > 1 )); then
      die "multiple .json files in ${CF_DIR} — set JOCKEY_VAST_UUID=<uuid> explicitly:
   ${found[*]}"
    fi
    TUNNEL_UUID="${found[0]%.json}"
  fi
  ok "tunnel UUID = ${TUNNEL_UUID}"
}

write_vast_config() {
  local cfg="${CF_DIR}/config.yml"
  local creds="${CF_DIR}/${TUNNEL_UUID}.json"
  [[ -f "$creds" ]] || die "credentials file missing: $creds"

  # MIGRATION_LOG problem #2: printf, never heredoc, for YAML.
  # MIGRATION_LOG problem #4: 127.0.0.1, never localhost.
  info "writing $cfg"
  {
    printf 'tunnel: %s\n' "$TUNNEL_UUID"
    printf 'credentials-file: %s\n' "$creds"
    printf '\n'
    printf 'ingress:\n'
    printf '  - hostname: video.%s\n' "$ZONE"
    printf '    service: http://127.0.0.1:%s\n' "$API_PORT"
    printf '  - service: http_status:404\n'
  } > "$cfg"
  ok "wrote $cfg"
}

start_vast_tunnel() {
  if session_exists "$VAST_TUNNEL_SESSION"; then
    ok "  ${VAST_TUNNEL_SESSION} already running"
    return
  fi
  info "starting inbound tunnel ${TUNNEL_NAME} in tmux '${VAST_TUNNEL_SESSION}'"
  tmux new -d -s "$VAST_TUNNEL_SESSION" \
    "cloudflared tunnel --config ${CF_DIR}/config.yml run ${TUNNEL_NAME}"
  ok "  ${VAST_TUNNEL_SESSION} started — attach with: tmux a -t ${VAST_TUNNEL_SESSION}"
}

# ----------------------------------------------------------- app
ensure_models_symlink() {
  # Lighthouse hardcodes /models/lighthouse — but the vast host-disk volume
  # is at /workspace/models so weights survive pod destroy+recreate. Symlink
  # bridges the two. Idempotent.
  if [[ ! -e /models ]]; then
    info "symlinking /models -> /workspace/models (Lighthouse expects /models)"
    ln -s /workspace/models /models
  elif [[ "$(readlink -f /models 2>/dev/null)" != "/workspace/models" ]]; then
    warn "/models already exists and isn't a symlink to /workspace/models"
    warn "  (current: $(readlink -f /models)). Lighthouse warm-up may not find weights."
  else
    ok "/models -> /workspace/models already in place"
  fi
}

start_app() {
  ensure_models_symlink
  info "delegating to vast-bootstrap.sh all"
  bash "${SCRIPT_DIR}/vast-bootstrap.sh" all
}

# ----------------------------------------------------------- stop
stop_all() {
  for row in "${LISTENERS[@]}"; do
    local sess
    IFS='|' read -r sess _ _ <<<"$row"
    session_exists "$sess" && { info "killing $sess"; tmux kill-session -t "$sess"; } || true
  done
  session_exists "$VAST_TUNNEL_SESSION" && { info "killing $VAST_TUNNEL_SESSION"; tmux kill-session -t "$VAST_TUNNEL_SESSION"; } || true
  info "stopping app (vast-bootstrap.sh stop)"
  bash "${SCRIPT_DIR}/vast-bootstrap.sh" stop || true
}

# ----------------------------------------------------------- status
status() {
  echo
  info "tmux sessions"
  tmux list-sessions 2>/dev/null | sed 's/^/   /' || echo "   (none)"
  echo
  info "127.0.0.1 listeners"
  for row in "${LISTENERS[@]}"; do
    local sess host port
    IFS='|' read -r sess host port <<<"$row"
    if (echo >/dev/tcp/127.0.0.1/${port}) 2>/dev/null; then
      ok "  ${port} (${host}) reachable"
    else
      warn "  ${port} (${host}) not reachable"
    fi
  done
  echo
  info "uvicorn on :${API_PORT}"
  if curl -fsS --max-time 3 "http://127.0.0.1:${API_PORT}/health" >/dev/null 2>&1; then
    ok "  /health responds 200"
  else
    warn "  /health not responding"
  fi
  echo
  info "public reachability"
  if curl -fsS --max-time 5 "https://video.${ZONE}/health" >/dev/null 2>&1; then
    ok "  https://video.${ZONE}/health → 200"
  else
    warn "  https://video.${ZONE}/health did not respond — check ${VAST_TUNNEL_SESSION}"
  fi
}

# ----------------------------------------------------------- dispatch
cmd="${1:-all}"
case "$cmd" in
  env)
    ensure_env
    ;;
  listeners)
    ensure_tools
    ensure_cloudflared
    start_listeners
    ;;
  tunnel)
    ensure_tools
    ensure_cloudflared
    ensure_vast_credentials
    write_vast_config
    start_vast_tunnel
    ;;
  app)
    ensure_env
    start_app
    ;;
  stop)
    stop_all
    ;;
  status)
    status
    ;;
  all)
    ensure_tools
    ensure_cloudflared
    ensure_env
    start_listeners
    ensure_vast_credentials
    write_vast_config
    start_vast_tunnel
    start_app
    status
    ;;
  *)
    die "unknown command '$cmd' — try: all | env | listeners | tunnel | app | stop | status"
    ;;
esac
