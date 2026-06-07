# Thesis VTG experiment — InternVideo2 + R2 / DETR (isolated)

Offline tooling for the thesis upgrade of the moment-retrieval / sports-highlight
pipeline. **Fully isolated from the live agent runtime** — nothing here is
imported by `backend/video-service` (the indexing worker or API). Develop and
roll back freely; the deployed `CLIP + SlowFast + PANNs + CG-DETR` pipeline is
untouched until you decide to fold a result back in (see *Foldback* below).

## The plan (decided 2026-06-03)

| Component | Current (deployed) | Thesis target |
|---|---|---|
| Visual backbone | CLIP + SlowFast | **InternVideo2-1B** (frozen, features cached) |
| Grounding head | CG-DETR (full) | **R2-style PEFT adapter** (~2.7M / 1.5% trainable) — the fine-tuned module |
| Baseline | — | CG-DETR retrained on the *same* InternVideo2 features |
| SOTA ceiling | — | **SG-DETR** (download checkpoint; reproduce, don't retrain) |
| Audio cue | PANNs | kept, separate stream (tool decomposition) |

Hardware: a single **RTX 3090 24GB**. The backbone is frozen and features are
extracted offline, so the 6B model never sits in the training loop — only the
~2.7M-param adapter trains, which fits 24GB with room to spare. (MLLM grounding
— Mr.BLIP / LLaVA-MR — was ruled out: needs 4–8×A100-80GB and mostly can't do
highlight detection.)

## Files

| File | What it does |
|---|---|
| `download_sg_detr_assets.sh` | gdown SG-DETR checkpoints + InternVideo2-1b features (URLs verified public 2026-06-03) |
| `iv2_feature_extractor.py` | single-video InternVideo2-1B feature extractor → `.npz` |
| `iv2_batch_extract.py` | batch extractor over a video dir (`--skip-existing`, loads encoder once) |
| `requirements.txt` | gdown / decord / opencv / numpy (torch + IV2 encoder pinned separately) |

These are the `jockey.open_source.training.iv2_feature_extractor` /
`iv2_batch_extract` modules the `m2_iv2_qd_detr_colab.ipynb` notebook already
calls (Steps 6–7). The notebook was written against them; this implements them.

## Getting the assets (no need to train SG-DETR yourself)

```bash
pip install -r requirements.txt
# Smallest useful pull: QVHighlights checkpoint + IV2 features only
ASSETS=qvh bash download_sg_detr_assets.sh ./assets/sg_detr
# Everything (multi-GB; InterVid-MR pretrain features are the big one):
bash download_sg_detr_assets.sh ./assets/sg_detr
```

SG-DETR ships **both** "w/ PT" (pretraining-boosted, the 74.2 R1 / 58.8 mAP
ceiling) and plain checkpoints, plus ready-made `iv2_1b_*` features for
QVHighlights/Charades/TACoS/TVSum/YouTubeHL. So you can (a) evaluate its
checkpoint directly on the 3090 (inference fits 24GB), and (b) train your
R2-adapter / CG-DETR baseline on the *same* InternVideo2 features SG-DETR uses,
making the comparison apples-to-apples.

## Encoder backends (for extracting features on YOUR OWN sports videos)

The released `iv2_1b_*` features cover the public benchmarks. To extract for
your own clips, pick a backend (`--backend` / `IV2_BACKEND`):

- **`sgdetr` (recommended, WIRED)** — reuses SG-DETR's shipped InternVideo2-1b
  encoder so features are byte-compatible with the released `iv2_1b_*` set.
  `_SGDetrEncoder` imports their `VideoInference` (TorchScript model via
  `torch.jit.load`) + `VideoTransforms` (ImageNet norm, 224 center-crop) and
  feeds `[1,C,T,H,W]` clips. Setup:
  ```bash
  git clone https://github.com/ai-forever/sg-detr vendor/sg-detr
  pip install -r vendor/sg-detr/features-extractor/requirements.txt
  ASSETS=weights bash download_sg_detr_assets.sh ./assets/sg_detr   # traced video_encoder.pt
  export IV2_SGDETR_REPO=$PWD/vendor/sg-detr/features-extractor
  export IV2_SGDETR_VIDEO_CKPT=$PWD/assets/sg_detr/fe_weights/video_encoder.pt
  ```
- **`hf`** — OpenGVLab InternVideo2 stage-2 (1B) via its own package +
  checkpoint (`IV2_HF_CKPT`). The checkpoint is **`OpenGVLab/InternVideo2-Stage2_1B-224p-f4`**
  (verified on HF 2026-06-03; this is SG-DETR's "InterVidV2-1b", `f4` = 4 frames/clip).
  Two gotchas: (1) the repo is **gated `auto`** — log into HF, accept the terms on
  the model page once (instant), and have `HF_TOKEN` set, else downloads 401;
  (2) it ships **only a raw `.pt`** (no `config.json`/modeling code), so
  `AutoModel.from_pretrained` does NOT work — you must clone OpenGVLab's
  InternVideo2 repo to build the ViT and load the `.pt`. This friction is why
  `sgdetr` is the default. Reference seam only; verify the model API against
  your installed build.

By design **neither backend falls back to random features** — if a real encoder
can't be loaded the extractor fails loudly (matches the repo's stated rule in
`encoders/config.py`).

```bash
# single-clip smoke test (basketball/03.mp4) — prints shape, stats, PASS/FAIL
python -m jockey.open_source.training.test_extract_basketball

# batch over a folder (2-video smoke)
python -m jockey.open_source.training.iv2_batch_extract \
    --videos-dir ../../../video/basketball --out-dir features/iv2_sports \
    --skip-existing --limit 2
```

Output `.npz` layout (matches the notebook's `d["visual_features"]`):
`visual_features [n_clips, 512] float16`, `clip_length_sec`, `fps_sampled`.

**Validated on a 3090 (2026-06-03):** `03.mp4` → `(28, 512)`, 2s clips. The
`iv2_1b` features are **512-d and L2-normalized** (per-clip norm=1.0) — the
CLIP-aligned InternVideo2 space, not the 768-d raw ViT. So the downstream
R2/CG-DETR head's `feat_dim = 512`, and the features are already unit-norm.
The TorchScript `video_encoder.pt` (traced on torch 2.0.1) loads fine on modern
torch (2.6+cu124); pin `numpy<2`, use `opencv-python-headless`, and note decord
has no py3.12 wheels (the OpenCV decode fallback is used there).

## Foldback (when an experiment wins)

To put a trained head into production, swap it in at **one seam**:
`backend/video-service/main/services/lighthouse_service.py` — `LighthouseService`
currently loads `CGDETRPredictor(feature_name="clip_slowfast", ...)`. Folding
back means pointing that loader at the InternVideo2 features + the new head
checkpoint (and adding an InternVideo2 path to `pipeline/ingest.py`'s feature
precompute). Until then, the live pipeline is unaffected.

Outputs (`features/`, `runs/`, `data/`, `assets/`) are gitignored.
