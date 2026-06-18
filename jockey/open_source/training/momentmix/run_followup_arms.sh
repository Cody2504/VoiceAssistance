#!/bin/bash
# Follow-up arms for plan 2026-06-12 (consistency loss + span loss-space).
# Usage:  bash run_followup_arms.sh [cons|xx|all]
#   cons -> scratch_qvh_mmix_cons : mmix data + cross-view consistency (~26-30h)
#   xx   -> scratch_qvh_mmix_xx   : mmix data + (start,end)-space span L1 (~16h)
#   all  -> both, sequentially
# Each arm: train (160 epochs, seed 40, batch 128) -> best-ckpt copy -> eval.
# Baseline to beat: Arm B scratch_qvh_mmix = 54.17 mAP avg / 21.38 Short.
set -euo pipefail
cd /workspace/sg-detr
export TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD=1
export PYTHONPATH=/workspace/sg-detr
ulimit -n 65535

PY=/workspace/tvenv/bin/python
ROOT=/workspace/runs/sgdetr
ANN=/workspace/data/qvhighlights/annotation
FEAT=/workspace/models/sg_detr/features/custom_features

DATA_OVR="data.annotation_path_val=$ANN/highlight_val_release.jsonl \
data.annotation_path_test=$ANN/highlight_val_release.jsonl \
data.query_feat_dir_train=$FEAT/custom_text \
data.query_feat_dir_val=$FEAT/custom_text \
data.query_feat_dir_test=$FEAT/custom_text \
data.video_feat_dir_train=$FEAT/video \
data.video_feat_dir_val=$FEAT/video \
data.video_feat_dir_test=$FEAT/video"

COMMON="paths.root_dir=$ROOT ~callbacks.rich_progress_bar +trainer.enable_progress_bar=false"

run_eval () {  # task_name checkpoint
  $PY src/cli/eval.py --config-name eval.yaml "checkpoint=$2" "task_name=$1" \
    $COMMON $DATA_OVR "data.annotation_path_train=$ANN/highlight_train_release.jsonl" \
    data.batch_size=32 data.num_workers=4
}

train_arm () {  # task_name train_jsonl extra_overrides...
  local task=$1 jsonl=$2; shift 2
  $PY src/cli/train.py --config-name train.yaml "task_name=$task" is_local_run=True test=False \
    $COMMON $DATA_OVR "data.annotation_path_train=$jsonl" \
    data.batch_size=128 data.num_workers=8 "$@"
  RUN=$(ls -d "$ROOT/logs/$task/runs/"* | sort | tail -1)
  CKPT=$(ls "$RUN"/checkpoints/*.ckpt | head -1)
  cp "$CKPT" "$ROOT/${task}_best.ckpt"   # clean name: hydra chokes on '=' in paths
  echo "BEST_CKPT($task): $CKPT -> $ROOT/${task}_best.ckpt"
}

ARM=${1:-cons}

if [[ "$ARM" == "cons" || "$ARM" == "all" ]]; then
  echo "=== ARM: scratch_qvh_mmix_cons (consistency lambda=0.5) ==="
  train_arm scratch_qvh_mmix_cons "$ANN/hl_mmix_5_seed0.jsonl" \
    +data.dataset.emit_consistency_view=true model.runner.consistency_weight=0.5
  run_eval eval_scratch_qvh_mmix_cons "$ROOT/scratch_qvh_mmix_cons_best.ckpt"
fi

if [[ "$ARM" == "xx" || "$ARM" == "all" ]]; then
  echo "=== ARM: scratch_qvh_mmix_xx (span L1 in start/end space) ==="
  train_arm scratch_qvh_mmix_xx "$ANN/hl_mmix_5_seed0.jsonl" \
    losses.main_reg_losses.span_loss_space=xx
  run_eval eval_scratch_qvh_mmix_xx "$ROOT/scratch_qvh_mmix_xx_best.ckpt"
fi

echo "ALL DONE ($ARM)"
