#!/bin/bash
# 50-epoch PILOT of the consistency arm (plan 2026-06-12 Part 1).
# Compares against Arm B's logged curve at identical epochs (qvh_ab_records.csv).
# save_last=true -> if the pilot looks good, resume into the full 160-epoch run:
#   +resume_from=$ROOT/pilot_qvh_mmix_cons_last.ckpt trainer.max_epochs=160
set -euo pipefail
cd /workspace/sg-detr
export TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD=1
export PYTHONPATH=/workspace/sg-detr
ulimit -n 65535

PY=/workspace/tvenv/bin/python
ROOT=/workspace/runs/sgdetr
ANN=/workspace/data/qvhighlights/annotation
FEAT=/workspace/models/sg_detr/features/custom_features

$PY src/cli/train.py --config-name train.yaml task_name=pilot_qvh_mmix_cons_w20 \
  is_local_run=True test=False \
  trainer.min_steps=1 trainer.max_epochs=50 \
  callbacks.model_checkpoint.save_last=true \
  +data.dataset.emit_consistency_view=true model.runner.consistency_weight=0.5 \
  model.runner.consistency_warmup_epochs=20 \
  paths.root_dir=$ROOT ~callbacks.rich_progress_bar +trainer.enable_progress_bar=false \
  "data.annotation_path_train=$ANN/hl_mmix_5_seed0.jsonl" \
  "data.annotation_path_val=$ANN/highlight_val_release.jsonl" \
  "data.annotation_path_test=$ANN/highlight_val_release.jsonl" \
  "data.query_feat_dir_train=$FEAT/custom_text" \
  "data.query_feat_dir_val=$FEAT/custom_text" \
  "data.query_feat_dir_test=$FEAT/custom_text" \
  "data.video_feat_dir_train=$FEAT/video" \
  "data.video_feat_dir_val=$FEAT/video" \
  "data.video_feat_dir_test=$FEAT/video" \
  data.batch_size=128 data.num_workers=8

RUN=$(ls -d "$ROOT/logs/pilot_qvh_mmix_cons_w20/runs/"* | sort | tail -1)
cp "$RUN"/checkpoints/last.ckpt "$ROOT/pilot_qvh_mmix_cons_last.ckpt"
BEST=$(ls "$RUN"/checkpoints/*.ckpt | grep -v last | head -1)
cp "$BEST" "$ROOT/pilot_qvh_mmix_cons_best.ckpt"
echo "CKPTS: $BEST + last.ckpt copied to $ROOT"

$PY src/cli/eval.py --config-name eval.yaml \
  "checkpoint=$ROOT/pilot_qvh_mmix_cons_best.ckpt" task_name=eval_pilot_cons \
  paths.root_dir=$ROOT ~callbacks.rich_progress_bar +trainer.enable_progress_bar=false \
  "data.annotation_path_train=$ANN/highlight_train_release.jsonl" \
  "data.annotation_path_val=$ANN/highlight_val_release.jsonl" \
  "data.annotation_path_test=$ANN/highlight_val_release.jsonl" \
  "data.query_feat_dir_train=$FEAT/custom_text" \
  "data.query_feat_dir_val=$FEAT/custom_text" \
  "data.query_feat_dir_test=$FEAT/custom_text" \
  "data.video_feat_dir_train=$FEAT/video" \
  "data.video_feat_dir_val=$FEAT/video" \
  "data.video_feat_dir_test=$FEAT/video" \
  data.batch_size=32 data.num_workers=4

echo "PILOT DONE"
