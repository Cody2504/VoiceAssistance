#!/bin/bash
# From-scratch QVHighlights A/B: baseline vs offline MomentMix (gen_qvh_mmix).
# Paper-faithful regime (LA-DETR WACV26): random init, single dataset,
# augmentation present from step 0, identical recipe/seed across arms.
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

train_arm () {  # task_name train_jsonl
  $PY src/cli/train.py --config-name train.yaml "task_name=$1" is_local_run=True test=False \
    $COMMON $DATA_OVR "data.annotation_path_train=$2" \
    data.batch_size=128 data.num_workers=8
  RUN=$(ls -d "$ROOT/logs/$1/runs/"* | sort | tail -1)
  CKPT=$(ls "$RUN"/checkpoints/*.ckpt | head -1)
  cp "$CKPT" "$ROOT/$1_best.ckpt"   # clean name: hydra chokes on '=' in paths
  echo "BEST_CKPT($1): $CKPT -> $ROOT/$1_best.ckpt"
}

echo "=== [1/5] reference eval: released plain sgdetr_qvhighlights.ckpt ==="
run_eval eval_qvh_plain_released /workspace/models/sg_detr/checkpoints/sgdetr_qvhighlights.ckpt

echo "=== [2/5] Arm A: from-scratch baseline ==="
train_arm scratch_qvh_base "$ANN/highlight_train_release.jsonl"

echo "=== [3/5] eval Arm A best ==="
run_eval eval_scratch_qvh_base "$ROOT/scratch_qvh_base_best.ckpt"

echo "=== [4/5] Arm B: from-scratch + MomentMix ==="
train_arm scratch_qvh_mmix "$ANN/hl_mmix_5_seed0.jsonl"

echo "=== [5/5] eval Arm B best ==="
run_eval eval_scratch_qvh_mmix "$ROOT/scratch_qvh_mmix_best.ckpt"

echo "ALL DONE"
