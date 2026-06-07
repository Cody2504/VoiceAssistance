#!/usr/bin/env bash
# setup-pod.sh — Phase 1 bring-up of the IV2+SG-DETR video-service on a fresh vast pod.
# Run ON THE POD after `backend/` + `jockey/` are rsync'd to /workspace/VoiceAssistance.
# Deterministic + idempotent: deps, all model weights, TransNetV2 TF->pytorch conversion,
# PANN pre-seed, and vast.env (secrets pulled from the rsync'd backend/.env; S3 from args).
# Tunnels/services/reindex are Phase 2 (need box key + CF cert + DNS) — done separately.
#
# Usage on the pod:
#   bash /workspace/VoiceAssistance/backend/scripts/setup-pod.sh <S3_KEY_ID> <S3_SECRET>
set -uo pipefail
REPO=/workspace/VoiceAssistance
M=/workspace/models
S3_KEY="${1:?pass S3 access key id}"; S3_SECRET="${2:?pass S3 secret}"
log(){ echo -e "\n=== $* ==="; }

log "PEP-668: remove EXTERNALLY-MANAGED marker (py3.12 pods block uv/pip --system otherwise)"
rm -f /usr/lib/python3.*/EXTERNALLY-MANAGED 2>/dev/null || true
export PIP_BREAK_SYSTEM_PACKAGES=1

log "pip upgrade"; python3 -m pip install -U -q pip || true

log "core deps (vast-bootstrap install: torch cu124 + reqs + lighthouse weights)"
bash "$REPO/backend/scripts/vast-bootstrap.sh" install

log "extra deps (panns + hydra/omegaconf for the SG-DETR head)"
pip install -q panns_inference omegaconf hydra-core

log "SG-DETR fe_weights + head ckpt"
cd "$REPO/jockey/open_source/training"
ASSETS=weights bash download_sg_detr_assets.sh "$M/sg_detr"
[ -f "$M/sg_detr/checkpoints/sgdetr_qvhighlights_pt.ckpt" ] || \
  curl -fL "https://drive.usercontent.google.com/download?id=1KFuLQHPvoCExCDG-P7VByd5fOtFQ3x8S&export=download&confirm=t" \
       -o "$M/sg_detr/checkpoints/sgdetr_qvhighlights_pt.ckpt"

log "strip SG-DETR head -> pure state-dict (loads without sg-detr repo)"
if [ ! -f "$M/sg_detr/sgdetr_head_state_dict.pt" ]; then
  [ -d /workspace/sg-detr ] || git clone --depth 1 https://github.com/ai-forever/sg-detr.git /workspace/sg-detr
  PYTHONPATH=/workspace/sg-detr python3 -c "import torch;ck=torch.load('$M/sg_detr/checkpoints/sgdetr_qvhighlights_pt.ckpt',map_location='cpu',weights_only=False);sd={k[6:]:v for k,v in ck['state_dict'].items() if k.startswith('model.')};torch.save(sd,'$M/sg_detr/sgdetr_head_state_dict.pt');print('stripped',len(sd),'tensors')"
fi

log "pre-seed PANN CNN14 weights (skip the slow zenodo re-download)"
mkdir -p ~/panns_data
[ -f ~/panns_data/Cnn14_mAP=0.431.pth ] || cp "$M/lighthouse/Cnn14_mAP=0.431.pth" ~/panns_data/ 2>/dev/null || true

log "TransNetV2 weights (one-time TF-cpu venv conversion -> pure pytorch)"
if [ ! -f "$M/transnetv2/transnetv2-pytorch-weights.pth" ]; then
  [ -d /workspace/TransNetV2 ] || git clone --depth 1 https://github.com/soCzech/TransNetV2.git /workspace/TransNetV2
  [ -d /workspace/tfconv ] || python3 -m venv /workspace/tfconv
  /workspace/tfconv/bin/pip install -q --upgrade pip
  /workspace/tfconv/bin/pip install -q numpy==1.26.4 tensorflow-cpu
  /workspace/tfconv/bin/pip install -q torch --index-url https://download.pytorch.org/whl/cpu
  ( cd /workspace/TransNetV2/inference-pytorch && /workspace/tfconv/bin/python convert_weights.py )
  mkdir -p "$M/transnetv2" && cp /workspace/TransNetV2/inference-pytorch/transnetv2-pytorch-weights.pth "$M/transnetv2/"
fi

log "write vast.env (connections via 127.0.0.1 SSH tunnels; secrets from rsync'd backend/.env; S3 from args)"
ENVSRC="$REPO/backend/.env"
get(){ grep -E "^$1=" "$ENVSRC" | head -1 | cut -d= -f2- | tr -d '\r'; }
cat > "$REPO/backend/vast.env" <<EOF
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=15432
POSTGRES_USER=jockey
POSTGRES_PASSWORD=$(get POSTGRES_PASSWORD)
POSTGRES_DB=jockey
REDIS_HOST=127.0.0.1
REDIS_PORT=16379
QDRANT_HOST=127.0.0.1
QDRANT_PORT=6333
QDRANT_COLLECTION=jockey_shots
MINIO_ENDPOINT=https://s3.ap-southeast-1.amazonaws.com
MINIO_PUBLIC_ENDPOINT=https://s3.ap-southeast-1.amazonaws.com
MINIO_ROOT_USER=$S3_KEY
MINIO_ROOT_PASSWORD=$S3_SECRET
MINIO_REGION=ap-southeast-1
MINIO_BUCKET_VIDEOS=videoassistant-demo
MINIO_BUCKET_EDITS=videoassistant-demo
MINIO_BUCKET_THUMBS=videoassistant-demo
SECRET_KEY=$(get SECRET_KEY)
OPENROUTER_API_KEY=$(get OPENROUTER_API_KEY)
HF_TOKEN=$(get HF_TOKEN)
CORS_ALLOW_ORIGINS=http://localhost:5173,http://localhost:8085,https://app.voiceassistant.uk
GROUNDING_BACKEND=iv2
IV2_DEVICE=cuda
IV2_VIDEO_CKPT=$M/sg_detr/fe_weights/video_encoder.pt
IV2_TEXT_CKPT=$M/sg_detr/fe_weights/text_encoder.pt
IV2_SGDETR_HEAD_CKPT=$M/sg_detr/sgdetr_head_state_dict.pt
LIGHTHOUSE_DEVICE=cuda
LIGHTHOUSE_CG_DETR_CKPT=$M/lighthouse/clip_slowfast_cg_detr_qvhighlight.ckpt
LIGHTHOUSE_CLAP_QD_DETR_CKPT=$M/lighthouse/clap_qd_detr_clotho_moment.ckpt
LIGHTHOUSE_SLOWFAST_CKPT=$M/lighthouse/SLOWFAST_8x8_R50.pkl
LIGHTHOUSE_PANN_CKPT=$M/lighthouse/Cnn14_mAP=0.431.pth
SHOT_DETECTOR=transnet
TRANSNET_WEIGHTS=$M/transnetv2/transnetv2-pytorch-weights.pth
MODELS_DIR=$M
WORKER_COUNT=1
EOF
chmod 600 "$REPO/backend/vast.env"
echo "vast.env keys: $(grep -c = "$REPO/backend/vast.env")"
echo ""; echo "SETUP_PHASE1_DONE — next: Phase 2 (ssh-db tunnel, cf-video tunnel + DNS, start vs-api/vs-worker, re-index)"
