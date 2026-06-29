#!/bin/bash
# Reference-head crash probe: 1 clean epoch, plain data, use_reference_head=true.
# Confirms the 3-point center/width refinement runs without the negative-width
# crash and produces finite losses (cxw-native width=sigmoid can't go negative).
set -uo pipefail
cd /workspace/sg-detr
export TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD=1 PYTHONPATH=/workspace/sg-detr
ulimit -n 65535
PY=/workspace/tvenv/bin/python
ANN=/workspace/data/qvhighlights/annotation
FEAT=/workspace/models/sg_detr/features/custom_features
ROOT=/workspace/runs/sgdetr
$PY src/cli/train.py --config-name train.yaml task_name=probe_refhead1ep is_local_run=True test=False \
  paths.root_dir=$ROOT ~callbacks.rich_progress_bar +trainer.enable_progress_bar=false \
  ~callbacks.early_stopping ~callbacks.model_checkpoint \
  data.annotation_path_train=$ANN/highlight_train_release.jsonl \
  data.annotation_path_val=$ANN/highlight_val_release.jsonl data.annotation_path_test=$ANN/highlight_val_release.jsonl \
  data.query_feat_dir_train=$FEAT/custom_text data.query_feat_dir_val=$FEAT/custom_text data.query_feat_dir_test=$FEAT/custom_text \
  data.video_feat_dir_train=$FEAT/video data.video_feat_dir_val=$FEAT/video data.video_feat_dir_test=$FEAT/video \
  data.batch_size=128 data.num_workers=8 \
  model.detr_detector.use_reference_head=true \
  ++trainer.max_epochs=1 ++trainer.limit_val_batches=0 ++trainer.num_sanity_val_steps=0 ++trainer.log_every_n_steps=5
echo "PROBE_REFHEAD_EXIT=$?"
