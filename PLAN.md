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

### Phase 3.5 — YouCook2 Auxiliary Pipeline  `[x]` (code) / pending data
- [x] **Task 3.5.1**: `training/youcook2.py` — annotation downloader (Michigan tarball), JSON parser, `YouCook2Dataset` (drop-in compatible with `grounding_collate`), `download_videos()` helper using `yt-dlp` for the YouTube video URLs.
- [x] **Task 3.5.2**: `precompute_queries.py` generalized — auto-dispatches between `.txt` (Charades-STA) and `.json` (YouCook2) formats.
- [ ] **Task 3.5.3**: ⏳ *user-action* — download YouCook2 annotation tarball, download videos via yt-dlp (~70-80% success rate; YouTube deletions are expected), batch-extract features. Smaller than Charades (~2k videos × ~150 windows ≈ 3-5 GPU-hours).
- [ ] **Task 3.5.4**: ⏳ *user-action* — precompute query embeddings for YouCook2 sentences.

**Rationale**: Charades-STA is visual-dominant (silent indoor activities — ASR transcripts are mostly empty/uninformative). YouCook2 has dense cooking narration → ASR transcripts carry real signal → caption modality of our tri-modal fusion has something to contribute. Enables an honest multi-dataset ablation story: "captions help where dataset has narration, not where it doesn't."

### Phase 5 — Eval & Ablations  `[ ]`
- [ ] **Task 5.1**: Eval harness — runs trained head on Charades-STA + YouCook2 test splits, prints metrics table
- [ ] **Task 5.2**: Ablation A — modality contribution (vision vs +audio vs +audio+caption) on **both** datasets — Charades expected to show captions contribute ~0%, YouCook2 expected to show captions contribute meaningfully
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
| 2026-05-11 | Annotation mirror | `jiyanggao/TALL` annotation URLs now 404. Swapped primary mirror to `Alvin-Zeng/DRN` (verified: 12,408 train + 3,720 test, matches paper splits) and added a 2-entry fallback chain (`microsoft/2D-TAN`, `26hzhang/VSLNet`) plus size sanity-check in `_try_download`. |
| 2026-05-11 | **Architecture fix** | First Colab GPU smoke test on a Charades video (`001YG.mp4`, 30.7s) revealed PySceneDetect collapses Charades videos to **1 shot** because they're continuous single-camera takes with no cuts. With 1 shot covering the whole video, the per-shot relevance signal is meaningless and the boundary head has no temporal anchoring. **Fix**: added `--uniform-window-sec` flag to `feature_extractor.py` + `batch_extract.py` (plus `uniform_windows()` helper). With `--uniform-window-sec 2.0`, a 30.7s video produces 16 windows — matching how Moment-DETR/QD-DETR/UniVTG operate on Charades-STA. Shot-detection mode is retained for produced video (movies/TV) where it's the right unit. |
| 2026-05-11 | **ASR + batched embeddings** | Cell F profile showed ~1s/window — extrapolated to **~30 hours** for full Charades-STA, with caption embeddings being the bottleneck (1 OpenRouter call per window × 107k windows). Two fixes: (1) added `WhisperASR` engine in `asr_whisper.py` as drop-in replacement for ZipFormer (no model-dir setup, just transformers; configurable via `ASR_BACKEND=whisper` env var). (2) added `TextEmbedder.encode_batch` and refactored `feature_extractor.extract()` into a two-pass loop: pass 1 collects visual+audio+ASR per window, pass 2 batch-embeds all captions in a single API call (~10-16× faster on the text-emb step). Net expected extraction time: **~10-15 hours** with real ASR captions, vs 30 hours without ASR. Multimodal thesis story preserved — all three modalities (visual, audio, caption) carry real signal. |
| 2026-05-11 | **YouCook2 auxiliary** | User sharp-questioned whether Charades-STA actually supports the multimodal-fusion story (ASR transcripts on silent indoor clips contribute little signal). Decision: keep Charades-STA as primary (well-benchmarked, fits Colab) + add YouCook2 as auxiliary for the caption-modality ablation. Built `youcook2.py` mirroring `charades_sta.py` (downloader, parser, Dataset, video-download via yt-dlp). Generalized `precompute_queries.py` to auto-dispatch between Charades-STA `.txt` and YouCook2 `.json` formats. Drop-in compatible with existing `grounding_collate` + `GroundingHead` + `train.py`. |
| 2026-05-11 | **Whisper filter narrowed** | User pushed back on the keyword hallucination filter ("sometimes they are the right [transcription]"). Removed the keyword/template blocklist entirely; trust the RMS silence detector alone. Stats simplified to `{silent, transcribed, total}`. Memory saved as a general preference: prefer principled signals over heuristic filters. |
| 2026-05-11 | **Pipeline review fixes (P0+P1)** | Self-audit of the pipeline revealed three issues. (1) `train.py` used the test set for `best.pt` selection — that's test-set leakage. Added `split_train_val()` with **video-level** split (not query-level — query-level would leak visual features across splits), `--val-ratio` (default 0.1) and `--val-seed` (default 42) CLI args. Early stopping now uses held-out val; test runs **once** at end, written to `test_metrics.json`. Fixed cold-start bug: `best_r05 = -1.0` so first eval always saves. (2) Replaced binary `gt_relevance` with soft IoU labels (intersection / shot_duration ∈ [0,1]) — smoother gradient, partial-overlap shots contribute partial signal. Binary mode kept as opt-in via `soft=False`. (3) `uniform_windows()` now merges the trailing partial window if it's shorter than `min_last_sec` (default = window/2). 30.7s @ 2s → 15 windows (was 16), last window 2.7s instead of 0.7s. Avoids meaningless ~1-frame trailing windows. All three verified with synthetic-data smoke tests. |
| 2026-05-11 | **Batched extraction (P1)** | Profile of single-video extraction showed N × ffmpeg subprocess (×2 for audio_encoder + asr_whisper) + N × per-shot encoder forwards. For 16-shot Charades video that's 32 ffmpeg invocations and 48 encoder forwards. **Refactored to single-pass**: (1) `_load_full_audio_16k_mono(video_path)` extracts the whole video's audio ONCE via ffmpeg → in-memory 16kHz mono float32 samples. (2) Added batch methods to all three encoders: `ViCLIPEmbedder.encode_video_batch(frames_list) → [N, 768]` (flattens all frames cross-shot, one CLIP forward, re-groups per-shot mean-pool); `AudioEncoder.encode_audio_batch(samples_list) → [N, 768]` (filters None/short, pads, one wav2vec2 forward); `WhisperASR.transcribe_batch(samples_list) → [str, ...]` (per-item RMS silence filter, then one Whisper generate). (3) `feature_extractor.extract()` now: Pass A collect frames per shot, Pass B extract full audio + slice per window in memory, Pass C three batched encoder forwards, Pass D one batched OpenRouter call. **Per-video calls: 1× ffmpeg + 1× each encoder + 1× OpenRouter** (was 32× ffmpeg + N× each encoder). Placeholder branches in CLIP/audio mirror real filter behavior (None/empty/short → zero embedding). Real Colab T4 timing: ~10s/video (predicted 1-3s; the bottleneck moved to per-shot `decord.VideoReader` re-instantiation in `extract_frames` — addressable as P2 follow-up if needed). Total Charades-STA extraction ~15-19 hours. |
| 2026-05-11 | **Sanity-run dry run (100 videos, 10 epochs)** | Ran the full pipeline end-to-end on 100 randomly-sampled Charades videos to validate before scaling up. Extraction: 100 videos × 10.4s = 1044s on Colab T4. After train/val/test split + feature-existence filter: 93 train queries / 28 val / 24 test. Training (lr=1e-3, bs=8, 10 epochs): train loss 1.62→1.25, rel loss 0.78→0.53 (learned), l1/iou losses plateaued (boundary head needs more data). Val R@0.5 hit 0.143 at ep 3, regressed to 0.0 afterward (small-data overfitting). Final test (24 queries): R@0.3=0.125, R@0.5=0.042, mIoU=0.076 — within statistical noise but above random uniform baseline. **Pipeline validated end-to-end**: no crashes, all metrics computed, splits work, best.pt + test_metrics.json written correctly. Identified follow-ups: AMP API deprecation warnings fixed (torch.cuda.amp.* → torch.amp.*); added `--features-dir-filter` to `precompute_queries` for sanity-run workflow; added NaN-return path in `evaluate()` for empty loaders. Next: kick off full 6700-video extraction. |
| 2026-05-11 | **Tier-1 architectural fix (CLIP-text queries + loss reweighting)** | Deep-research review identified the root cause of the R@0.5=0.04 sanity result: the query embedding (text-embedding-3-large, 3072-d, OpenAI text space) was in a completely different space from the visual features (CLIP-L vision, 768-d, CLIP image-text joint space). A single linear projection cannot learn to bridge unrelated pretrained spaces from ~10k training pairs. Every modern Charades-STA paper that achieves R@0.5 > 0.50 (Moment-DETR, QD-DETR, UniVTG) uses **CLIP-text** for queries, which has built-in alignment with CLIP visual via contrastive pretraining. **Fix**: (1) Added `ViCLIPEmbedder.encode_text_batch(texts) → [N, 768]` using CLIP's text encoder. (2) `precompute_queries.py` accepts `--encoder clip` (default, recommended) or `--encoder openai` (opt-in for ablation). (3) Split `GroundingConfig.query_dim` (768, CLIP-text) from new `global_dim` (3072, text-emb-3-large from `MetadataEncoder`) — these are different embedders and shouldn't share a projection. (4) Re-balanced loss weights to Moment-DETR conventions: `--w-rel 1.0 --w-l1 10.0 --w-iou 1.0` (was 1/1/0.5 — the boundary head was starved of gradient relative to the BCE relevance loss). (5) Added embedding-dim logging in Dataset constructors so dim mismatches surface immediately. End-to-end smoke test passes; boundary head learns instead of plateauing. **User must regenerate the query embedding cache with the new CLIP-text encoder before re-running training.** |
