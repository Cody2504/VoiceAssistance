#!/bin/bash
# Arm G: from-scratch QVH, MomentMix data + ReferenceRefinementHead WITH the
# RDSA center->score role-split (use_reference_head=true + use_center_score=true).
# Targets the RANKING half of the short failure (rank-1 center-in-GT 10%) that the
# role-less Arm F left flat. Arm-D/F-identical recipe, capped 100ep for SCREENING.
# Compare ep<=100 vs Arm F (role-less ref head) AND Arm D@90 (short 22.28/full 54.22):
# success = short-mAP clears Arm F/Arm D by a real margin with full + R1@0.7 not down.
set -uo pipefail
cd /workspace/sg-detr
export TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD=1 PYTHONPATH=/workspace/sg-detr
ulimit -n 65535
PY=/workspace/tvenv/bin/python
ROOT=/workspace/runs/sgdetr
ANN=/workspace/data/qvhighlights/annotation
FEAT=/workspace/models/sg_detr/features/custom_features
TASK=scratch_qvh_mmix_refscore
DATA_OVR="data.annotation_path_val=$ANN/highlight_val_release.jsonl \
data.annotation_path_test=$ANN/highlight_val_release.jsonl \
data.query_feat_dir_train=$FEAT/custom_text data.query_feat_dir_val=$FEAT/custom_text data.query_feat_dir_test=$FEAT/custom_text \
data.video_feat_dir_train=$FEAT/video data.video_feat_dir_val=$FEAT/video data.video_feat_dir_test=$FEAT/video"
COMMON="paths.root_dir=$ROOT ~callbacks.rich_progress_bar +trainer.enable_progress_bar=false"

echo "=== TRAIN Arm G (mmix + reference head + center->score) ==="
$PY src/cli/train.py --config-name train.yaml task_name=$TASK is_local_run=True test=False \
  $COMMON $DATA_OVR "data.annotation_path_train=$ANN/hl_mmix_5_seed0.jsonl" \
  data.batch_size=128 data.num_workers=8 \
  model.detr_detector.use_reference_head=true model.detr_detector.use_center_score=true \
  ++trainer.max_epochs=100
echo "TRAIN_EXIT=$?"

RUN=$(ls -d "$ROOT/logs/$TASK/runs/"* | sort | tail -1)
CKPT=$(ls "$RUN"/checkpoints/*.ckpt 2>/dev/null | head -1)
echo "BEST_RAW_CKPT: $CKPT"
cp "$CKPT" "$ROOT/${TASK}_best.ckpt"

echo "=== EVAL Arm G best ==="
$PY src/cli/eval.py --config-name eval.yaml "checkpoint=$ROOT/${TASK}_best.ckpt" "task_name=eval_$TASK" \
  $COMMON $DATA_OVR "data.annotation_path_train=$ANN/highlight_train_release.jsonl" \
  data.batch_size=32 data.num_workers=4 \
  ++model.detr_detector.use_reference_head=true ++model.detr_detector.use_center_score=true
echo "EVAL_EXIT=$?"
echo "ARM_G_DONE"
