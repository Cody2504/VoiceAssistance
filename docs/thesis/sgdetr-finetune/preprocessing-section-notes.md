# Preprocessing section content (thesis 3.x Tiền xử lý dữ liệu)

Design decision: ALL preprocessing offline, once (frozen InternVideo2-1B) — ~150GB raw video → 2.2GB feature store; training never touches pixels; enables single-RTX-3090 fine-tune.

## Video
- Non-overlapping 2-second clips, max 75 clips (150 s) per video (QVHighlights convention)
- Frames → 224×224, normalized → frozen IV2-1B video tower → 512-d per clip, L2-normalized
- + TEF (Temporal Endpoint Features): concat [t_start/L, t_end/L] → 514-d model input (positional information for the DETR head)
- Padding + attention masks (src_vid_mask) to the 75-clip cap

## Text
- BPE tokenize, truncate to 40 tokens → frozen text tower → 512-d per-token, L2-normalized, src_txt_mask

## Annotations
- JSONL: 7,217 train / 1,549 val queries; moment windows [start, end] on the 2 s grid (≤10/query); per-clip saliency (3 annotators, 4-point scale) for HD
- Windows → normalized (center, width) spans = DETR regression targets

## "Augmentation" equivalent
- Image-space augmentation not applicable (features precomputed)
- In-model regularization instead: dropout 0.1, droppath 0.15, proj dropout 0.5, denoising anchors with span noise 0.5 (perturbed GT spans the decoder learns to correct)

## Production parity (lifecycle)
- Same preprocessing runs live at ingest: TransNetV2 shots → 2 s clips → same frozen IV2 encoder → per-video cached features (features/{video_id}/iv2/visual.npy)

Numbers: clip_len=2s; max_video_length=75; vid_dim=514 (512+TEF); txt_dim=512; max_query_length=40; features archive 2.07GB zip → custom_features/{video, custom_text}
