#!/usr/bin/env bash
# Ingest a folder of lecture videos into a new Index for the cross-video
# knowledge-graph (networkx / videoRAG) E2E test.
#
# Flow: login -> create Index -> upload each NN.mp4 -> poll until "ready"
#       -> add to Index in order -> print the KG backfill command.
#
# Uploads go through the GATEWAY (:8085), which proxies /api/v1/videos to the
# video-service (on the GPU pod via the Cloudflare tunnel). JWTs validate across
# services via the shared SECRET_KEY.
#
# Usage:
#   EMAIL=you@example.com PASSWORD=secret ./scripts/ingest_lecture_series.sh
#   # or, if you already have an access token:
#   TOKEN=eyJ... ./scripts/ingest_lecture_series.sh
#
# Env overrides:
#   BASE_URL      default http://localhost:8085/api/v1
#   VIDEO_DIR     default video/linear_algebra
#   INDEX_TITLE   default "Essence of Linear Algebra"
#   INDEX_LANG    default en        (use "vi" for Vietnamese transcripts/KG)
#   POLL_TRIES    default 120       (× POLL_SLEEP = max wait per video)
#   POLL_SLEEP    default 15        (seconds)
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8085/api/v1}"
VIDEO_DIR="${VIDEO_DIR:-video/linear_algebra}"
INDEX_TITLE="${INDEX_TITLE:-Essence of Linear Algebra}"
INDEX_LANG="${INDEX_LANG:-en}"
POLL_TRIES="${POLL_TRIES:-120}"
POLL_SLEEP="${POLL_SLEEP:-15}"

# Descriptive titles parallel to 01.mp4 .. 08.mp4 (used as the upload filename so
# citations read "Vectors (Ch1) @ 6:00" instead of "01.mp4 @ 6:00").
declare -A TITLES=(
  [01]="Vectors (Ch1)"
  [02]="Linear combinations, span, basis (Ch2)"
  [03]="Linear transformations and matrices (Ch3)"
  [04]="Matrix multiplication as composition (Ch4)"
  [05]="Three-dimensional linear transformations (Ch5)"
  [06]="The determinant (Ch6)"
  [07]="Inverse matrices, column space, null space (Ch7)"
  [08]="Nonsquare matrices as transformations (Ch8)"
)

# --- tiny JSON field reader (python3, no jq dependency) ---
jget() { python3 -c "import sys,json;d=json.load(sys.stdin)
p='$1'.split('.')
for k in p:
    d=d.get(k) if isinstance(d,dict) else None
print('' if d is None else d)"; }

command -v curl >/dev/null || { echo "curl required"; exit 1; }
[ -d "$VIDEO_DIR" ] || { echo "VIDEO_DIR not found: $VIDEO_DIR"; exit 1; }

# --- auth ---
if [ -z "${TOKEN:-}" ]; then
  if [ -n "${EMAIL:-}" ] && [ -n "${PASSWORD:-}" ]; then
    echo "→ logging in as $EMAIL"
    TOKEN=$(curl -fsS -X POST "$BASE_URL/auth/login" -H 'Content-Type: application/json' \
      -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" | jget data.tokens.access_token)
  fi
fi
if [ -z "${TOKEN:-}" ]; then
  echo "No auth. Set TOKEN=… or EMAIL=… PASSWORD=…"
  echo "(Tip: log in via the web app, then copy localStorage 'tl_jockey_access'.)"
  exit 1
fi
AUTH=(-H "Authorization: Bearer $TOKEN")

# --- create index ---
echo "→ creating index: $INDEX_TITLE ($INDEX_LANG)"
INDEX_ID=$(curl -fsS -X POST "$BASE_URL/indexes" "${AUTH[@]}" -H 'Content-Type: application/json' \
  -d "{\"title\":\"$INDEX_TITLE\",\"description\":\"3Blue1Brown Essence of Linear Algebra — cross-video KG test\",\"language\":\"$INDEX_LANG\"}" \
  | jget data.id)
[ -n "$INDEX_ID" ] || { echo "index create failed"; exit 1; }
echo "  index_id = $INDEX_ID"

# --- upload all ---
declare -a VIDS=() KEYS=()
for f in $(ls "$VIDEO_DIR"/[0-9][0-9].mp4 | sort); do
  key=$(basename "$f" .mp4)
  name="${TITLES[$key]:-$key}.mp4"
  echo "→ uploading $f  as  \"$name\""
  vid=$(curl -fsS -X POST "$BASE_URL/videos" "${AUTH[@]}" \
    -F "file=@$f;type=video/mp4;filename=$name" | jget data.id)
  [ -n "$vid" ] || { echo "  upload failed for $f"; exit 1; }
  echo "  video_id = $vid"
  VIDS+=("$vid"); KEYS+=("$key")
done

# --- poll until ready ---
echo "→ waiting for indexing (status=ready)…"
for i in "${!VIDS[@]}"; do
  vid="${VIDS[$i]}"; key="${KEYS[$i]}"
  for ((t=1;t<=POLL_TRIES;t++)); do
    st=$(curl -fsS "$BASE_URL/videos/$vid" "${AUTH[@]}" | jget data.status)
    case "$st" in
      ready) echo "  [$key] ready"; break;;
      error) echo "  [$key] ERROR during indexing"; break;;
      *) printf "\r  [%s] %s (%d/%d)…   " "$key" "${st:-?}" "$t" "$POLL_TRIES"; sleep "$POLL_SLEEP";;
    esac
    [ "$t" -eq "$POLL_TRIES" ] && echo "  [$key] timed out waiting for ready"
  done
done

# --- add to index in order ---
echo "→ adding videos to index (in chapter order)…"
for i in "${!VIDS[@]}"; do
  vid="${VIDS[$i]}"; key="${KEYS[$i]}"
  curl -fsS -X POST "$BASE_URL/indexes/$INDEX_ID/videos" "${AUTH[@]}" -H 'Content-Type: application/json' \
    -d "{\"video_id\":\"$vid\",\"position\":null}" >/dev/null && echo "  + $key"
done

cat <<EOF

✓ Uploaded + indexed + attached 8 lectures to index:
    $INDEX_ID

Next — build the cross-video knowledge graph (runs where video-service lives,
i.e. the GPU pod, with KG_ENABLED=true and OPENROUTER_API_KEY set):

    docker exec jockey-video python -m main.scripts.backfill_kg --index $INDEX_ID
    # (or wherever the video-service container runs in your split deploy)

Then query the KG:
    curl -X POST $BASE_URL/indexes/$INDEX_ID/concepts/search "${AUTH[@]}" \\
      -H 'Content-Type: application/json' -d '{"query":"linear transformation","top_k":10}'
    # pick an entity_id, then:
    curl $BASE_URL/indexes/$INDEX_ID/entities/<ENTITY_ID>/mentions "${AUTH[@]}"
    curl "$BASE_URL/indexes/$INDEX_ID/entities/<ENTITY_ID>/related?direction=both&top_k=20" "${AUTH[@]}"

Or via chat (whole-index): POST $BASE_URL/chat/stream with {"index_id":"$INDEX_ID","message":"How does the determinant relate to linear transformations across these lectures?"}
EOF
