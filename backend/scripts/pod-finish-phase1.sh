/u#!/usr/bin/env bash
# pod-finish-phase1.sh — the bring-up steps on the 2026-06-10 pod (202.59.206.41:11466)
# that need explicit user execution (credential copy + external-repo code + tunnels).
# Everything else (deps in /venv/main, lighthouse/SG-DETR weight files, ViCLIP weights,
# vast.env with all six feature flags) is already done by the agent session.
#
# Run FROM the local machine (WSL):  bash backend/scripts/pod-finish-phase1.sh
set -uo pipefail
POD="-p 11466 root@202.59.206.41"
REPO_LOCAL=/mnt/d/MR-DETR/VoiceAssistance

echo "=== 1. credentials -> pod (Lightsail key + cloudflared cert) ==="
ssh $POD "mkdir -p /root/.cloudflared"
scp -P 11466 "$REPO_LOCAL/LightsailDefaultKey-ap-southeast-1.pem" root@202.59.206.41:/root/ls.pem
scp -P 11466 /root/.cloudflared/cert.pem root@202.59.206.41:/root/.cloudflared/cert.pem
ssh $POD "chmod 600 /root/ls.pem /root/.cloudflared/cert.pem"

echo "=== 2. external-code installs + conversions on the pod ==="
ssh $POD 'bash -s' <<'REMOTE'
set -uo pipefail
REPO=/workspace/VoiceAssistance; M=/workspace/models; PY=/venv/main/bin/python
export PATH=/venv/main/bin:$PATH

# lighthouse lib (pip from git, --no-deps — its setup.py pins ancient numpy)
uv pip install --python $PY -q --no-deps "lighthouse @ git+https://github.com/line/lighthouse.git@main"

# SG-DETR head -> pure state-dict (clone needed once for the model classes during load)
if [ ! -f "$M/sg_detr/sgdetr_head_state_dict.pt" ]; then
  [ -d /workspace/sg-detr ] || git clone --depth 1 -q https://github.com/ai-forever/sg-detr.git /workspace/sg-detr
  PYTHONPATH=/workspace/sg-detr $PY -c "import torch;ck=torch.load('$M/sg_detr/checkpoints/sgdetr_qvhighlights_pt.ckpt',map_location='cpu',weights_only=False);sd={k[6:]:v for k,v in ck['state_dict'].items() if k.startswith('model.')};torch.save(sd,'$M/sg_detr/sgdetr_head_state_dict.pt');print('stripped',len(sd),'tensors')"
fi

# TransNetV2 TF -> pytorch weights (one-time conversion in a tf-cpu venv)
if [ ! -f "$M/transnetv2/transnetv2-pytorch-weights.pth" ]; then
  [ -d /workspace/TransNetV2 ] || git clone --depth 1 -q https://github.com/soCzech/TransNetV2.git /workspace/TransNetV2
  [ -d /workspace/tfconv ] || python3 -m venv /workspace/tfconv
  /workspace/tfconv/bin/pip install -q --upgrade pip
  /workspace/tfconv/bin/pip install -q numpy==1.26.4 tensorflow-cpu
  /workspace/tfconv/bin/pip install -q torch --index-url https://download.pytorch.org/whl/cpu
  ( cd /workspace/TransNetV2/inference-pytorch && /workspace/tfconv/bin/python convert_weights.py )
  mkdir -p "$M/transnetv2" && cp /workspace/TransNetV2/inference-pytorch/transnetv2-pytorch-weights.pth "$M/transnetv2/"
fi

# cloudflared binary
command -v cloudflared >/dev/null || {
  curl -fsSL -o /usr/local/bin/cloudflared \
    https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
  chmod +x /usr/local/bin/cloudflared
}

echo EXTERNAL_STEPS_DONE
REMOTE

echo "=== 3. tunnels (tmux: ssh-db + cf-video) ==="
ssh $POD 'bash -s' <<'REMOTE'
set -uo pipefail
# DB/Redis/Qdrant tunnels to the Lightsail box (auto-restarting loop; tmux survives the agent session, not a pod reboot)
tmux kill-session -t ssh-db 2>/dev/null
# NB: the box's compose stack publishes pg/redis on HOST ports 15432/16379 already
tmux new-session -d -s ssh-db "while true; do ssh -i /root/ls.pem -o StrictHostKeyChecking=no -o ServerAliveInterval=30 -o ExitOnForwardFailure=yes -N -L 15432:127.0.0.1:15432 -L 16379:127.0.0.1:16379 -L 6333:127.0.0.1:6333 ubuntu@54.254.37.244; sleep 5; done"
sleep 4
# cloudflared: new tunnel for this pod, re-point video.voiceassistant.uk
T=vast-video-id1
cloudflared tunnel list 2>/dev/null | grep -q " $T " || cloudflared tunnel create $T
cloudflared tunnel route dns --overwrite-dns $T video.voiceassistant.uk
tmux kill-session -t cf-video 2>/dev/null
tmux new-session -d -s cf-video "cloudflared tunnel run --url http://localhost:1101 $T"
sleep 3
tmux ls
# quick checks
timeout 8 bash -c 'until pg_isready -h 127.0.0.1 -p 15432 2>/dev/null; do sleep 1; done' || \
  /venv/main/bin/python - <<'PY'
import socket
for p in (15432, 16379, 6333):
    s = socket.socket(); s.settimeout(3)
    try: s.connect(("127.0.0.1", p)); print(f"tunnel :{p} OK")
    except Exception as e: print(f"tunnel :{p} FAIL {e}")
    finally: s.close()
PY
echo TUNNELS_DONE
REMOTE

echo ""
echo "ALL DONE — tell the agent to continue (it will run migrations, start vs-api/vs-worker, then wipe + re-index)."
