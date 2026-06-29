#!/bin/bash
# Arm E: from-scratch QVH, MomentMix data + LAD (length-aware decoder, Part-2-alt).
# Identical to Arm B/D recipe (seed 40, batch 128, 160ep) + class-balanced selection
# (num_queries=40, M=4) + class-conditioned matching (lad_borders).
set -uo pipefail
cd /workspace/sg-detr
export TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD=1 PYTHONPATH=/workspace/sg-detr
ulimit -n 65535
PY=/workspace/tvenv/bin/python
ROOT=/workspace/runs/sgdetr
ANN=/workspace/data/qvhighlights/annotation
FEAT=/workspace/models/sg_detr/features/custom_features
TASK=scratch_qvh_mmix_lad
BORDERS='[0.089,0.21,0.5]'
DATA_OVR="data.annotation_path_val=$ANN/highlight_val_release.jsonl \
data.annotation_path_test=$ANN/highlight_val_release.jsonl \
data.query_feat_dir_train=$FEAT/custom_text data.query_feat_dir_val=$FEAT/custom_text data.query_feat_dir_test=$FEAT/custom_text \
data.video_feat_dir_train=$FEAT/video data.video_feat_dir_val=$FEAT/video data.video_feat_dir_test=$FEAT/video"
COMMON="paths.root_dir=$ROOT ~callbacks.rich_progress_bar +trainer.enable_progress_bar=false"

echo "=== TRAIN Arm E (mmix + LAD) ==="
$PY src/cli/train.py --config-name train.yaml task_name=$TASK is_local_run=True test=False \
  $COMMON $DATA_OVR "data.annotation_path_train=$ANN/hl_mmix_5_seed0.jsonl" \
  data.batch_size=128 data.num_workers=8 \
  model.num_queries=40 "model.query_selector.lad_borders=$BORDERS" "losses.matcher.lad_borders=$BORDERS"
echo "TRAIN_EXIT=$?"

RUN=$(ls -d "$ROOT/logs/$TASK/runs/"* | sort | tail -1)
CKPT=$(ls "$RUN"/checkpoints/*.ckpt 2>/dev/null | head -1)
echo "BEST_RAW_CKPT: $CKPT"
cp "$CKPT" "$ROOT/${TASK}_best.ckpt"

echo "=== EVAL Arm E best ==="
$PY src/cli/eval.py --config-name eval.yaml "checkpoint=$ROOT/${TASK}_best.ckpt" "task_name=eval_$TASK" \
  $COMMON $DATA_OVR "data.annotation_path_train=$ANN/highlight_train_release.jsonl" \
  data.batch_size=32 data.num_workers=4 \
  model.num_queries=40 "++model.query_selector.lad_borders=$BORDERS"
echo "EVAL_EXIT=$?"
echo "ARM_E_DONE"
