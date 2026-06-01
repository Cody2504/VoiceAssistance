#!/usr/bin/env bash
# setup-laptop.sh — one-shot, idempotent bring-up of the laptop side of the
# VoiceAssistance stack: WSL2 docker compose + cloudflared tunnel "jockey-wsl"
# that exposes pg / redis / qdrant / minio / iam / token over voiceassistant.uk.
#
# Usage (from backend/ or anywhere — paths are resolved from script location):
#   bash backend/scripts/setup-laptop.sh              # full bring-up
#   bash backend/scripts/setup-laptop.sh env          # just (re)create backend/.env
#   bash backend/scripts/setup-laptop.sh cloudflared  # install + tunnel + DNS
#   bash backend/scripts/setup-laptop.sh docker       # build + compose up
#   bash backend/scripts/setup-laptop.sh tunnel       # run cloudflared in foreground
#   bash backend/scripts/setup-laptop.sh status
#
# Re-runnable: every step checks state before acting.

set -euo pipefail

# ----------------------------------------------------------- paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_DIR="$(cd "${BACKEND_DIR}/.." && pwd)"
CF_DIR="${HOME}/.cloudflared"
TUNNEL_NAME="jockey-wsl"
ZONE="voiceassistant.uk"

# host:port pairs the tunnel exposes. Format: <hostname>|<tcp|http>|<port>
INGRESS=(
  "pg.${ZONE}|tcp|15432"
  "redis.${ZONE}|tcp|16379"
  "qdrant.${ZONE}|tcp|6333"
  "minio.${ZONE}|http|9000"
  "iam.${ZONE}|http|1100"
  "token.${ZONE}|http|1103"
)

# ----------------------------------------------------------- pretty
RED=$'\e[31m'; GRN=$'\e[32m'; YLW=$'\e[33m'; BLU=$'\e[34m'; NC=$'\e[0m'
info() { printf "%s[*]%s %s\n" "$BLU" "$NC" "$*"; }
ok()   { printf "%s[OK]%s %s\n" "$GRN" "$NC" "$*"; }
warn() { printf "%s[!!]%s %s\n" "$YLW" "$NC" "$*"; }
die()  { printf "%s[ERR]%s %s\n" "$RED" "$NC" "$*" >&2; exit 1; }

# ----------------------------------------------------------- env file
ensure_env() {
  local target="${BACKEND_DIR}/.env"
  local root_env="${REPO_DIR}/.env"
  local template="${BACKEND_DIR}/.env.example"

  if [[ -f "$target" ]]; then
    ok "backend/.env already exists — leaving it alone"
  elif [[ -f "$root_env" ]]; then
    # MIGRATION_LOG problem #5: compose looks for .env next to the compose file.
    info "copying $root_env → $target (compose picks .env next to compose file)"
    cp "$root_env" "$target"
    ok "backend/.env created from project-root .env"
  else
    info "no .env found — generating one from .env.example with random secrets"
    cp "$template" "$target"
    local secret pg_pw minio_pw
    secret=$(openssl rand -hex 32)
    pg_pw=$(openssl rand -hex 16)
    minio_pw=$(openssl rand -hex 16)
    sed -i "s|^SECRET_KEY=.*|SECRET_KEY=${secret}|"                       "$target"
    sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${pg_pw}|"          "$target"
    sed -i "s|^MINIO_ROOT_PASSWORD=.*|MINIO_ROOT_PASSWORD=${minio_pw}|"   "$target"
    warn "edit $target and fill: OPENAI_API_KEY, OPENROUTER_API_KEY, HF_TOKEN"
    warn "then re-run: bash $0 cloudflared"
    exit 1
  fi

  # Append the tunnel-related vars idempotently if missing.
  add_kv() {
    local key="$1" val="$2"
    if ! grep -qE "^${key}=" "$target"; then
      printf '%s=%s\n' "$key" "$val" >> "$target"
      ok "  added $key=$val"
    fi
  }
  add_kv VIDEO_UPSTREAM "video.${ZONE}:443"
  add_kv VIDEO_SERVICE_BASE_URL "https://video.${ZONE}"
}

# ----------------------------------------------------------- cloudflared install
ensure_cloudflared() {
  if command -v cloudflared >/dev/null 2>&1; then
    ok "cloudflared already installed ($(cloudflared --version 2>&1 | head -1))"
    return
  fi
  info "installing cloudflared via Cloudflare apt repo"
  sudo mkdir -p --mode=0755 /usr/share/keyrings
  curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg \
    | sudo tee /usr/share/keyrings/cloudflare-main.gpg >/dev/null
  local codename
  codename=$(lsb_release -cs 2>/dev/null || echo jammy)
  echo "deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared ${codename} main" \
    | sudo tee /etc/apt/sources.list.d/cloudflared.list >/dev/null
  sudo apt-get update -qq
  sudo apt-get install -y cloudflared
  ok "cloudflared installed"
}

# ----------------------------------------------------------- cloudflared login
ensure_cert() {
  if [[ -f "${CF_DIR}/cert.pem" ]]; then
    ok "cert.pem already present at ${CF_DIR}/cert.pem"
    return
  fi
  info "running 'cloudflared tunnel login' — pick the ${ZONE} zone in the browser"
  cloudflared tunnel login
  [[ -f "${CF_DIR}/cert.pem" ]] || die "login did not produce cert.pem — re-run"
  ok "cert.pem written"
}

# ----------------------------------------------------------- tunnel create
ensure_tunnel() {
  if cloudflared tunnel list 2>/dev/null | awk 'NR>2 {print $2}' | grep -qx "$TUNNEL_NAME"; then
    ok "tunnel '${TUNNEL_NAME}' already exists"
  else
    info "creating tunnel '${TUNNEL_NAME}'"
    cloudflared tunnel create "$TUNNEL_NAME"
  fi
  TUNNEL_UUID=$(cloudflared tunnel list 2>/dev/null \
    | awk -v n="$TUNNEL_NAME" '$2==n {print $1}' | head -1)
  [[ -n "${TUNNEL_UUID:-}" ]] || die "could not resolve UUID for tunnel ${TUNNEL_NAME}"
  ok "tunnel UUID = ${TUNNEL_UUID}"

  # Catch the "tunnel exists in Cloudflare but local <UUID>.json is gone"
  # case early. Cloudflare doesn't store the secret half — once the JSON is
  # deleted the only fix is `cloudflared tunnel delete + create` again.
  local creds="${CF_DIR}/${TUNNEL_UUID}.json"
  if [[ ! -f "$creds" ]]; then
    die "tunnel '${TUNNEL_NAME}' (${TUNNEL_UUID}) exists in Cloudflare but its
   credentials file is missing locally: $creds
   Fix:
     cloudflared tunnel delete -f ${TUNNEL_NAME}
     bash $0 cloudflared
   The new tunnel will get a new UUID; this script's 'route dns -f' step
   will repoint all 6 hostnames automatically."
  fi
}

# ----------------------------------------------------------- config.yml
write_config() {
  local cfg="${CF_DIR}/config.yml"
  local creds="${CF_DIR}/${TUNNEL_UUID}.json"
  [[ -f "$creds" ]] || die "credentials file missing: $creds"

  # MIGRATION_LOG problem #2: heredoc auto-indent broke the YAML. Use printf
  # so every line is column-0 exactly as we wrote it.
  # MIGRATION_LOG problem #4: use 127.0.0.1, never localhost (IPv6 bug).
  info "writing $cfg"
  {
    printf 'tunnel: %s\n' "$TUNNEL_UUID"
    printf 'credentials-file: %s\n' "$creds"
    printf '\n'
    printf 'ingress:\n'
    for row in "${INGRESS[@]}"; do
      local host proto port
      IFS='|' read -r host proto port <<<"$row"
      printf '  - hostname: %s\n' "$host"
      printf '    service: %s://127.0.0.1:%s\n' "$proto" "$port"
    done
    printf '  - service: http_status:404\n'
  } > "$cfg"
  ok "wrote $cfg"
}

# ----------------------------------------------------------- DNS routes
route_dns() {
  for row in "${INGRESS[@]}"; do
    local host
    IFS='|' read -r host _ _ <<<"$row"
    info "routing DNS ${host} → ${TUNNEL_NAME}"
    # -f overwrites a previous CNAME for the same hostname.
    cloudflared tunnel route dns -f "$TUNNEL_NAME" "$host" \
      || warn "  route may already exist; continuing"
  done
}

# ----------------------------------------------------------- docker stack
# Laptop-only services. video-service + video-worker deliberately omitted —
# they run on the vast GPU pod. Bringing them up here causes MIGRATION_LOG
# problem #11: the laptop worker dequeues from Redis faster than the vast
# worker and fails every job with import errors.
LAPTOP_SERVICES=(postgres redis qdrant minio minio-init iam agent-service token-usage gateway)

docker_up() {
  command -v docker >/dev/null 2>&1 || die "docker missing — install Docker Desktop with WSL2 integration"
  cd "$BACKEND_DIR"

  if ! docker image inspect jockey-base:dev >/dev/null 2>&1; then
    info "building jockey-base:dev (one-time, ~5-10 min)"
    make base-build
  else
    ok "jockey-base:dev present"
  fi

  info "docker compose build (only laptop-side services)"
  docker compose build "${LAPTOP_SERVICES[@]}"

  # Defensive: if a previous run brought up video-service/worker (or they
  # exist from before this script), kill them now so they don't race vast.
  info "removing any local video-service / video-worker containers (vast owns these)"
  docker compose -f docker-compose.yml -f docker-compose.local.yml rm -sf video-service video-worker 2>/dev/null || true

  # --no-deps is critical: gateway and agent-service both declare
  # depends_on: video-service in docker-compose.yml. Without --no-deps,
  # compose would auto-build + start video-service even though we didn't
  # list it (and that build is currently broken on the laptop because
  # the video-service Dockerfile has a /shared path bug — and we don't
  # care, vast owns it). Every laptop dependency is in LAPTOP_SERVICES
  # explicitly, so --no-deps loses nothing.
  info "docker compose up -d --no-deps (laptop services only: ${LAPTOP_SERVICES[*]})"
  docker compose -f docker-compose.yml -f docker-compose.local.yml up -d --no-deps "${LAPTOP_SERVICES[@]}"

  info "waiting 10s for healthchecks…"
  sleep 10
  docker compose ps
}

# ----------------------------------------------------------- run tunnel
run_tunnel_fg() {
  info "starting cloudflared in foreground (Ctrl-C to stop)"
  info "for production use: sudo cloudflared service install"
  cloudflared tunnel --config "${CF_DIR}/config.yml" run "$TUNNEL_NAME"
}

# ----------------------------------------------------------- status
status() {
  echo
  info "cloudflared"
  command -v cloudflared >/dev/null && cloudflared --version 2>&1 | head -1 || echo "  (not installed)"
  [[ -f "${CF_DIR}/cert.pem" ]] && ok "  cert.pem present" || warn "  cert.pem missing — run 'login'"
  [[ -f "${CF_DIR}/config.yml" ]] && ok "  config.yml present" || warn "  config.yml missing"
  echo
  info "tunnels"
  cloudflared tunnel list 2>/dev/null || echo "  (cannot list)"
  echo
  info "docker stack"
  ( cd "$BACKEND_DIR" && docker compose ps 2>/dev/null ) || echo "  (compose not up)"
  echo
  info "external reachability — run from outside the LAN to truly verify"
  for row in "${INGRESS[@]}"; do
    local host proto
    IFS='|' read -r host proto _ <<<"$row"
    if [[ "$proto" == "http" ]]; then
      if curl -fsS --max-time 5 "https://${host}/health" >/dev/null 2>&1; then
        ok "  https://${host}/health → 200"
      else
        warn "  https://${host}/health did not respond (may not have /health)"
      fi
    fi
  done
}

# ----------------------------------------------------------- dispatch
cmd="${1:-all}"
case "$cmd" in
  env)         ensure_env ;;
  cloudflared) ensure_cloudflared; ensure_cert; ensure_tunnel; write_config; route_dns ;;
  docker)      docker_up ;;
  tunnel)      ensure_tunnel; run_tunnel_fg ;;
  status)      status ;;
  all)
    ensure_env
    ensure_cloudflared
    ensure_cert
    ensure_tunnel
    write_config
    route_dns
    docker_up
    status
    echo
    ok "setup complete. start the tunnel with:"
    echo "    bash $0 tunnel"
    echo "  or install as a system service:"
    echo "    sudo cloudflared service install"
    ;;
  *)
    die "unknown command '$cmd' — try: all | env | cloudflared | docker | tunnel | status"
    ;;
esac
