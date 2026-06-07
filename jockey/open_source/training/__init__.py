"""Thesis-side training & feature extraction for the InternVideo2 + R2/DETR
video-temporal-grounding experiment.

ISOLATED from the live agent runtime (``backend/video-service``): nothing in
this package is imported by the indexing worker or the API. It exists so the
thesis experiments — InternVideo2-1B feature extraction, R2-adapter / CG-DETR
training, SG-DETR baselining — can be developed and rolled back freely without
touching the deployed CLIP+SlowFast+PANNs+CG-DETR pipeline.

See ``README.md`` in this directory for the full plan and the foldback path.
"""
