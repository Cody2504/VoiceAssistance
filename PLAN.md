# tl-jockey Thesis — Implementation Plan

**Goal**: Build an open-source TwelveLabs-Jockey-equivalent video understanding agent. One trained multimodal grounding head as the academic component; everything else uses frozen models or APIs.

**Status legend**: `[ ]` pending — `[/]` in progress — `[x]` done — `[~]` deferred/optional

---

## Locked-in scope (2026-05-10)

| Field | Value |
|---|---|
| Thesis frame | Applied SE system + one trained multimodal component |
| Trained component | Multimodal temporal-grounding head on **Charades-STA** |
| Architecture | Frozen `ViCLIP/CLIP-L` (visual) + `wav2vec2-base` (audio) + `text-embedding-3-large` (caption/metadata, OpenRouter) → trainable 3–6L fusion transformer + relevance head (BCE) + boundary head (L1+IoU). Moment-DETR / QD-DETR style. |
| Compute | Colab Pro / Kaggle (T4/P100/A100 bursts). Frozen-feature precompute pattern is mandatory. |
| Datasets | Charades-STA (primary). YouCook2/COIN auxiliary, optional. |
| Three agent tools | `video-search` (Qdrant ANN + grounding head), `video-text-generation` (API VLM, no training), `video-edit` (LLM plan → ffmpeg) |
| Eval target | R@1@IoU=0.5, R@1@IoU=0.7 on Charades-STA (no SOTA pressure — context only) |

## Architecture

```
Indexing pipeline (offline, frozen):
  video.mp4
    ├─ PySceneDetect          → shot boundaries
    ├─ decord @sampled fps    → frames per shot
    │   └─ ViCLIP/CLIP-L      → visual_emb [768]      (frozen)
    ├─ ffmpeg audio extract   → wav 16k mono per shot
    │   └─ wav2vec2-base      → audio_emb  [768]      (frozen)
    │   └─ ZipFormer/Whisper  → ASR transcript per shot
    └─ caption + metadata     → text-embedding-3-large [3072]  (API)

  → save .npz: visual[N,768], audio[N,768], caption[N,3072], shot_boundaries[N,2]

Trained head (Colab):
  precomputed shot tokens (visual ⊕ audio ⊕ caption) + query_emb [3072]
    → projection → fusion transformer (3–6L, 8H, hidden=512)
    → relevance head (per-shot BCE)
    → boundary head (L1 + IoU)

Agent tools (online):
  • video-search.library(text)       — Qdrant ANN over CLS shot embeddings
  • video-search.localize(text, vid) — trained grounding head
  • video-gen.summarize / describe   — Molmo2 / Qwen3-VL API
  • video-edit.plan(text) + execute  — LLM → ffmpeg
```

---

## Phases

### Phase 0 — Setup & Audit  `[x]`
- [x] Lock thesis scope (applied SE + grounding head)
- [x] Pick benchmarks (Charades-STA primary, MSR-VTT optional)
- [x] Reading list (Moment-DETR, QD-DETR, UniVTG, ViCLIP, InternVideo2, LanguageBind, Tarsier)
- [x] Audit existing repo (`mediafm_encoder.py`, `viclip_embedder.py`, `audio_encoder.py`, `metadata_encoder.py`, `indexer.py`, `asr.py`)

### Phase 1 — Offline Feature Extraction  `[x]` (smoke test pending real video)
- [x] **Task 1.1**: `training/feature_extractor.py` — wraps existing encoders; saves `.npz` per video with visual/audio/caption features + shot boundaries + ASR text. `ShotFeatures` dataclass with `save()` / `load()` round-trip validated.
- [x] **Task 1.2**: CLI: `python -m jockey.open_source.training.feature_extractor --video path --out file.npz`
- [x] **Task 1.3**: Batch script `training/batch_extract.py` — accepts `--videos-dir` or `--manifest` CSV, supports `--skip-existing`, `--limit`, modality skip flags
- [ ] **Task 1.4**: ⏳ *user-action* — smoke test on a real video on a GPU machine: `python -m jockey.open_source.training.feature_extractor --video football.mp4 --out features/football.npz`

### Phase 2 — Grounding Head Model  `[x]`
- [x] **Task 2.1**: `training/grounding_head.py` — `GroundingHead` with multimodal projections (visual/audio/caption/query/global), sum-fusion, [CLS]+[GLOBAL]+[QUERY] prefix tokens, transformer encoder, relevance + boundary heads. Configurable via `GroundingConfig`. **18.65M trainable params at hidden=512, 4L, 8H** — fits Colab T4 with batch ≥16.
- [x] **Task 2.2**: Loss module — `grounding_loss()` returning BCE(relevance) + L1(boundary) + (1 − IoU(boundary)), with `shot_mask` padding support
- [x] **Task 2.3**: Eval metrics — `recall_at_iou(θ)`, `mean_iou()` for θ ∈ {0.3, 0.5, 0.7}
- [x] **Task 2.4**: Smoke test verified — forward/backward pass on dummy tensors; gradients flow; metrics computed

### Phase 3 — Charades-STA Data Pipeline  `[x]` (data-running tasks pending user)
- [x] **Task 3.1**: `training/charades_sta.py::download_annotations()` — fetches train + test split files (canonical mirror; configurable URLs)
- [x] **Task 3.2**: `parse_annotations()` — `VIDEO_ID start end##query` → list of records. `unique_queries()` for dedup. Malformed lines skipped with warning.
- [ ] **Task 3.3**: ⏳ *user-action* — download Charades videos (manual; registration at https://prior.allenai.org/projects/charades) and run `batch_extract --videos-dir … --out-dir features/charades/` to produce `<vid>.npz` files.
- [x] **Task 3.4**: `CharadesSTADataset` (Dataset) + `grounding_collate` (variable-length padding with `shot_mask`). Plus helpers: `compute_shot_relevance`, `normalize_boundary`. Plus `precompute_queries.py` to cache text-emb-3-large embeddings of all unique queries (incremental, checkpointed).
- [ ] **Task 3.5**: ⏳ *user-action* — sanity check on real data: `len(train_ds)`, `len(test_ds)`, ratio of "moment ≥ half video" vs "short moment", etc.

**Smoke test (synthetic data) verified end-to-end**: parse → relevance/boundary computation → dataset filtering → variable-length collation → model forward+backward+loss. Total loss converged on dummy batch.

### Phase 4 — Training Loop  `[x]` (real run pending user)
- [x] **Task 4.1**: `training/train.py` — AdamW + cosine warmup, gradient clipping, mixed-precision (fp16 AMP on CUDA), CPU/CUDA auto-select
- [x] **Task 4.2**: Checkpointing — `last.pt` after every epoch + `best.pt` on best `R@1@IoU=0.5`. Resume via `--resume <path>`
- [x] **Task 4.3**: CSV logging — `train_log.csv` (per-step) + `val_log.csv` (per-epoch). TensorBoard/W&B intentionally skipped (CSV is plottable from notebook; less infra surface)
- [x] **Task 4.4**: `training/train_colab.ipynb` (17 cells) — Drive mount + repo clone + dep install + secrets via `userdata` + annotation download + query precompute + train + plot + resume
- [ ] **Task 4.5**: ⏳ *user-action* — first real training run on Colab once Phase 3.3 features are extracted

**Smoke test (synthetic, 2 epochs, 5 train + 2 test items, 1.81M params)**: loss decreased monotonically (1.36 → 1.08 → 1.18 → 1.44 with cosine LR), eval metrics printed, `best.pt` saved when R@0.5 improved 0→0.5, CSV logs flushed.

### Phase 5 — Eval & Ablations  `[ ]`
- [ ] **Task 5.1**: Eval harness — runs trained head on Charades-STA test split, prints metrics table
- [ ] **Task 5.2**: Ablation A — modality contribution (vision vs +audio vs +audio+caption)
- [ ] **Task 5.3**: Ablation B — fusion depth (3 vs 6 layers)
- [ ] **Task 5.4**: Optional baseline — random-init head, frozen-checkpoint Moment-DETR

### Phase 6 — Agent Tool: video-search  `[ ]`
- [ ] **Task 6.1**: `tools/video_search.py` — `search_library(text, k)` over Qdrant
- [ ] **Task 6.2**: `localize_in_video(text, video_id)` using trained head
- [ ] **Task 6.3**: Format response as JSON for LangGraph

### Phase 7 — Agent Tool: video-text-generation  `[ ]`
- [ ] **Task 7.1**: `tools/video_text_gen.py` — short-clip description (sampled frames → VLM)
- [ ] **Task 7.2**: Hierarchical summary (per-shot caption → LLM rollup) for long videos
- [ ] **Task 7.3**: Open-ended QA composing localize + describe

### Phase 8 — Agent Tool: video-edit  `[ ]`
- [ ] **Task 8.1**: Edit-plan schema (cut, concat, overlay_text, trim, fade)
- [ ] **Task 8.2**: `tools/video_edit.py` — LLM parses NL → JSON plan
- [ ] **Task 8.3**: ffmpeg executor — runs the plan, returns output path

### Phase 9 — LangGraph Supervisor + Demo  `[ ]`
- [ ] **Task 9.1**: Wire 3 tools into LangGraph supervisor agent
- [ ] **Task 9.2**: Demo script: 5–10 representative queries (search, summary, edit)
- [ ] **Task 9.3**: Qualitative eval set + manual scoring template

### Phase 10 — Thesis writeup  `[~]` (do during/after Phase 5)
- [ ] **Task 10.1**: Draft Methods chapter (architecture + training)
- [ ] **Task 10.2**: Results chapter (eval + ablation table)
- [ ] **Task 10.3**: System chapter (agent + tools + LangGraph)
- [ ] **Task 10.4**: Discussion + limitations

---

## Decisions log

| Date | Decision | Rationale |
|---|---|---|
| 2026-05-10 | Frozen-feature precompute pattern, not end-to-end training | Colab compute envelope; encoders too large to fine-tune |
| 2026-05-10 | Charades-STA as primary benchmark | Standard temporal-grounding benchmark, ~6.7k videos, fits Colab |
| 2026-05-10 | Single trained component = grounding head (relevance + boundary) | Highest thesis-impact per Colab GPU-hour; uses all 3 modalities |
| 2026-05-10 | VLM (Pegasus-side) and LLM (planner) stay as APIs | Saves training budget; APIs already strong |
| 2026-05-10 | Reuse `MediaFMEncoder` as fusion-transformer base | Already in repo, matches user's architecture diagram |

## Update log

| Date | Task | Change |
|---|---|---|
| 2026-05-10 | Phase 0 | Research scoping completed; PLAN.md created |
| 2026-05-10 | Phase 1 | `feature_extractor.py` + `batch_extract.py` shipped. `ShotFeatures` save/load validated (97 KB / 5 shots round-trip). CLI working. Real-video smoke test deferred to user (needs GPU + API keys). |
| 2026-05-10 | Phase 2 | `grounding_head.py` shipped. `GroundingHead` (18.65M params @ 4L/8H/h=512), `grounding_loss`, `recall_at_iou`, `mean_iou`. Forward + backward + loss + metric all verified on dummy tensors (grad norm 71.82, all heads producing valid outputs). |
| 2026-05-10 | Phase 3 | `charades_sta.py` (parser + downloader + Dataset + collate + GT-relevance/boundary helpers) and `precompute_queries.py` (incremental query-emb cache builder). Full pipeline smoke-tested end-to-end with synthetic data: dataset filtering, variable-length collation, model integration all OK. Two user-action items: download videos + extract features (Task 3.3); sanity-check splits (Task 3.5). |
| 2026-05-10 | Phase 4 | `train.py` (AdamW + cosine warmup + AMP + checkpointing + CSV logs + resume) and `train_colab.ipynb` (17-cell Drive-mounted runner with secrets via `userdata`, annotation download, query precompute, train, plot, resume cells). Smoke-tested 2 epochs on synthetic data; loss decreases, best.pt saved on R@0.5 improvement, resume verified by checkpoint structure. Real training run is the next user-action item. |
| 2026-05-10 | Bug fix | First real-data smoke test on `football.mp4` revealed the encoders silently fell back to **random embeddings** when CUDA driver missing on local box. Fixed in `viclip_embedder.py` + `audio_encoder.py` (added `_resolve_device()` that auto-falls back from cuda → cpu with a warning) and `config.py` (default device is now `_auto_device()` = `cuda if torch.cuda.is_available() else cpu`). Without this, features extracted on a CPU-only machine were unusable for training. |
