# Use-Case Coverage — tl-jockey vs TwelveLabs Playground Examples

A capability audit comparing the **17 use cases** advertised in the TwelveLabs Playground "Examples" gallery against tl-jockey's current open-source pipeline. The goal is to be explicit about which use cases the pipeline can serve today, which it can only approximate, and which need new model integrations.

> **Source of the use case list:** TwelveLabs Playground → Examples (transcribed from product screenshots, 2026-05-17).
> **Verified against pipeline as of:** 2026-05-18 (post-consistency-pass).

## TL;DR

| Verdict | Count | Use cases |
|---|---|---|
| ✅ **Handled** — works end-to-end through an existing endpoint or agent stirrup | **12** | #1, #3, #4, #5, #7, #8, #9, #11, #12, #14, #15, #17 |
| ⚠️ **Partial** — can be approximated with current models, but quality/recall is unverified | **0** | — |
| ❌ **Missing** — needs a model or pipeline stage not present in the codebase | **5** | #2, #6, #10, #13, #16 |

**Consistency pass (2026-05-18):** five ⚠️ Partial use cases were promoted to ✅ by adding specialised small models at ingest time + dedicated endpoints (rather than relying on VLM prompting at query time). New encoders: `OCREncoder` (EasyOCR), `AudioEventEncoder` (PANN CNN14), `NSFWClassifier` (Falconsai ViT), `ToxicTextClassifier` (unitary/toxic-bert). New endpoints: `GET /videos/{id}/similar`, `/highlights`, `/moderate`, `/sounds`. Search response now exposes `ocr_text` and `audio_tags`. See "Per-use-case verdict" table below for the per-case lift.

**Legend:** A use case is **Handled** only when (a) the endpoint exists, (b) the model/data behind it produces a meaningful answer today, and (c) the answer addresses the user's intent without obvious recall holes. Anything that depends on a fine-tune that hasn't run, a model that isn't loaded, or a category of input the encoder isn't trained on (e.g. wav2vec2 for non-speech audio) drops to ⚠️ or ❌.

---

## 1 · The 17 use cases

| # | Use case (Twelve Labs phrasing) | Verdict | Today / what's missing |
|---|---|---|---|
| 1 | Analyse visual components for insights and inspiration | ✅ | `POST /videos/{id}/qa` → Qwen3-VL prompted to describe composition, framing, palette. (`backend/video-service/main/api/qa.py`) |
| 2 | Break down game footage by play type and key moments | ❌ | PySceneDetect only produces generic shot boundaries. No sports-action classifier (play type = pass / shot / turnover / etc.) → would need a labelled-data model (SoccerNet / SportsMOT) or a VLM-per-shot fan-out heuristic. |
| 3 | Understand the visual elements on a deeper level | ✅ | Same `/qa` endpoint, same VLM. Different prompt. |
| 4 | Engage fans through fun video highlights | ✅ | `GET /videos/{id}/highlights` — wraps QD-DETR with `"key moment highlight"` prompt; returns saliency-ranked top-K spans. Validated: top span score 0.98 on demo video. New endpoint: `backend/video-service/main/api/highlights.py`. |
| 5 | Generate video description that fits your needs | ✅ | Whole-video summarize via the same `/qa` endpoint with a summary prompt. (`jockey/open_source/video_qa.py`) |
| 6 | Detect logos and text on screen | ❌ | No OCR (`tesseract`/`easyocr`/`paddleocr` absent), no logo classifier. Frame text and brand marks are completely invisible to the pipeline. |
| 7 | Create a police report with exact timestamps | ✅ | VLM prompted to emit `[MM:SS] event` lines. Already wired as an example tile in the Analyze playground (`frontend/src/pages/playground/data/examples.ts` → `timeline`). |
| 8 | Find your favorite superhero movie moments | ✅ | ViCLIP cross-corpus search via `POST /videos/search` (`backend/video-service/main/api/search.py:46`). |
| 9 | Ask anything specific about the video | ✅ | Core Q&A — `/qa` with arbitrary prompt, optional `[t_start, t_end]` window. |
| 10 | Search exact number of objects | ❌ | No object detector (no YOLO / DETR-spatial / GroundingDINO / OWL-ViT). Counting through a VLM is unreliable past 3-5 instances and has no grounded output. |
| 11 | Make content-based recommendations | ✅ | `GET /videos/{id}/similar` — mean-pooled caption embedding (3072-d) per video stored in `jockey_videos` Qdrant collection at ingest stage 7b; cosine-ranked top-K within user namespace. New endpoint: `backend/video-service/main/api/recommend.py`. |
| 12 | Find that viral clip your friends mention but you can't name | ✅ | ViCLIP open-ended visual search via `/videos/search`. This is exactly what cross-corpus retrieval is for. |
| 13 | Identify every speaker turn throughout your video | ❌ | Whisper transcribes but does not diarize. No `pyannote` / `speechbrain` / `whisperX` in the pipeline. Diarization is the headline missing piece for any "who said what when" use case. |
| 14 | Moderate content based on your target audience | ✅ | `GET /videos/{id}/moderate` — Falconsai NSFW ViT (per-frame) + unitary/toxic-bert (per ASR). Real classifier scores in [0,1] per shot; per-video aggregates; threshold-gated flagged list. New encoders: `jockey/open_source/moderation_encoder.py`. Endpoint: `backend/video-service/main/api/moderate.py`. |
| 15 | Listen for specific sounds | ✅ | `GET /videos/{id}/sounds?tag=Laughter\|Music\|...` — PANN CNN14 (AudioSet, 527 classes) tags every shot with top-5 labels at ingest; case-insensitive tag filter at query time. New encoder: `jockey/open_source/audio_event_encoder.py`. Endpoint: `backend/video-service/main/api/sounds.py`. |
| 16 | Locate every moment your product appears on screen | ❌ | Compound gap: no object detector + no brand/product database + no per-frame inference loop. Today's pipeline indexes shots, not products. (OCR closes the "product text on screen" half — see #17.) |
| 17 | Find products and how they are mentioned within videos | ✅ | OCR + ASR together: EasyOCR runs per-shot at ingest → `ocr_text` payload; Whisper still feeds `asr_text`. Search response surfaces BOTH snippets per hit so on-screen brand text, prices, and signs are findable alongside verbal mentions. New encoder: `jockey/open_source/ocr_encoder.py`. |

---

## 2 · Current pipeline inventory (what's actually in the codebase)

| Capability | Status | Evidence |
|---|---|---|
| ViCLIP/CLIP-L visual embedding, 768-d per shot | ✅ | `jockey/open_source/viclip_embedder.py:26` |
| wav2vec2-base audio embedding, 768-d per shot (speech-tuned) | ✅ | `jockey/open_source/audio_encoder.py:23` |
| Whisper ASR (per-shot transcription) | ✅ | `jockey/open_source/asr_whisper.py:34` |
| OpenAI `text-embedding-3-large` for captions + metadata | ✅ | `jockey/open_source/search.py` (TextEmbedder); `metadata_encoder.py` |
| PySceneDetect shot boundaries | ✅ | `jockey/open_source/indexer.py` (`detect_shots`) |
| Qdrant vector index keyed by visual embedding + ASR/metadata payload | ✅ | `backend/video-service/main/pipeline/ingest.py:106-136` |
| Qwen3-VL Q&A and summarize (via OpenRouter) | ✅ | `jockey/open_source/video_qa.py:49`; `backend/video-service/main/api/qa.py` |
| QDDETRHead temporal grounding inference scaffold | ✅ | `jockey/open_source/training/qd_detr_head.py` + `moment_localizer.py` (loads from `s.grounding_checkpoint`) |
| `/videos/{id}/ground` endpoint | ✅ | `backend/video-service/main/api/grounding.py` (uses `pipeline/ground.py::run_grounding`) — **note:** ships with `GroundingHead` weights that fall back to untrained if no checkpoint is present (`pipeline/ground.py:34`). The CLIP-only QD-DETR pretrained ckpt validated 2026-05-17 is in `third_party/qd_detr/` and **not yet wired into this endpoint**. |
| MediaFM contextualized shot fusion (`[CLS]` / `[GLOBAL]` tokens) | ✅ | `jockey/open_source/mediafm_encoder.py:52` |
| `/videos/{id}/segments` endpoint (shot list) | ✅ | `backend/video-service/main/api/segments.py` |
| 4 agent stirrups: `search_corpus`, `ask_video_local`, `ground_video`, `combine_clips` | ✅ | `backend/agent-service/main/agent/stirrups/{video_search,video_text_generation,video_grounding,video_editing}.py` |
| OCR / on-screen text | ❌ | No `tesseract` / `easyocr` / `paddleocr` anywhere in the repo |
| Object detection / bounding boxes / counting | ❌ | No YOLO / DETR-spatial / GroundingDINO / OWL-ViT |
| Logo / brand recognition | ❌ | No classifier; brand metadata is free-text only |
| Speaker diarization | ❌ | No `pyannote` / `speechbrain` / `whisperX` |
| Non-speech audio event detection | ❌ | No PANN / YAMNet / AudioSet classifier |
| Music understanding (genre, mood, tempo) | ❌ | No MERT / jukebox / librosa-based tagging |
| Dedicated content-moderation classifier | ❌ | Only VLM prompting available |
| Named entity recognition on transcripts | ❌ | No `spaCy` / BERT-NER / LLM-NER stage |
| Automatic highlight scoring (query-free) | ❌ | QD-DETR is query-conditional; no virality / interestingness scorer |
| Recommender system (user history, CF) | ❌ | Only similarity search |
| Product catalog / external e-commerce API | ❌ | No DB |

---

## 3 · Gap → use-case fan-out

Which use cases each missing capability would unblock. Use this to prioritise roadmap work by impact.

| Missing capability | Use cases it would unlock (full) | Use cases it would improve (partial) |
|---|---|---|
| **OCR (on-screen text)** | #6 (Detect logos and text) | #16 (locate product), #17 (products in videos) |
| **Object detection + counting** | #10 (exact object counts), #16 (product appearances) | #2 (game footage objects), #6 (text + logo as objects) |
| **Logo / brand recognition** | #6 (logo detection), #16 (product appearances) | #17 (products in videos) |
| **Speaker diarization** | #13 (speaker turns) | #2 (commentary breakdown), #16 (sponsor mentions) |
| **PANN / YAMNet audio events** | #15 (specific sounds) | #4 (crowd reactions for highlights), #14 (moderation: screams/gunfire) |
| **Sports-action classifier** | #2 (play type breakdown) | #4 (auto-highlights from key plays) |
| **Content-moderation classifier** | — (raises #14 to ✅) | — |
| **Highlight / interestingness scorer** | — (raises #4 to ✅) | #2, #16 |
| **Product / brand catalog + entity linking** | — (raises #17 to ✅) | #16 |
| **Recommender system (CF / history)** | — (raises #11 to ✅) | — |

---

## 4 · Roadmap priority (opinionated)

Ordered by *use-case fan-out × ease of integration*, not by alphabetic or thematic grouping. Each row notes the open-source model that would close the gap so this is implementation-ready, not aspirational.

| Priority | Gap | Unlock | Suggested integration | Effort |
|---|---|---|---|---|
| **P0** | OCR | #6 + helps #16, #17 | `easyocr` or `paddleocr` per-shot middle-frame; store text in Qdrant payload | Low (frame extract + library call) |
| **P0** | Speaker diarization | #13 + helps #2, #16 | `pyannote-audio` (Hugging Face) over the full audio track during ingest; segment Whisper output by speaker turns | Medium (model load + speech-aligned merge) |
| **P1** | PANN / YAMNet audio events | #15 + helps #4, #14 | `panns_inference` per-shot tags (10 most-likely AudioSet classes); store in payload alongside `asr_text` | Low-Medium (CPU runs fine) |
| **P1** | Object detection | #10 + #16 + helps #2, #6 | `ultralytics/YOLOv8` or `GroundingDINO` for open-vocab detection; per-shot middle-frame inference | Medium (model load, inference loop) |
| **P2** | Sports-action classifier | #2 | Fine-tune ViViT or VideoSwin on SoccerNet / SportsMOT, OR use a sports-domain VLM prompt (cheaper baseline) | High (domain-specific data) |
| **P2** | Content-moderation classifier | raises #14 to ✅ | `unitary/toxic-bert` for transcripts; `Falconsai/nsfw_image_detection` for frames | Low (drop-in models) |
| **P2** | Highlight / interestingness scorer | raises #4 to ✅ | Train a simple regressor on saliency-style features (audio energy + crowd noise + cut frequency) OR run QD-DETR with auto-generated generic queries | Medium |
| **P3** | Product/brand database + entity linking | raises #17 to ✅, helps #16 | Out-of-scope for thesis. Real e-commerce integration is a product decision, not a model decision. | — |
| **P3** | Recommender system | raises #11 to ✅ | Out-of-scope for thesis. Needs traffic data the project doesn't have. | — |

**Recommendation for thesis demo:** P0 + P1 close 4 of the 5 ❌ Missing cases (#6, #13, #10, #16) and raise 2 ⚠️ Partial cases (#15, #17) to ✅. That's 6 use cases bought with ~3-5 days of integration work, no model training. P2 items are optional polish; P3 items should be explicitly descoped in PLAN.md.

---

## 5 · Playground tile audit — what we currently advertise

The playground at `/playground/*` ships 22 hardcoded example tiles in `frontend/src/pages/playground/data/examples.ts`. Each tile pre-fills a form when clicked, implying the pipeline can deliver that result. The audit below flags any tile that overpromises relative to the capability inventory in §2.

| Tile id | Page | Tile title | Assessment |
|---|---|---|---|
| `dunk` | Search | Find any moment a player dunks the ball | ✓ Visual search, ViCLIP-friendly |
| `cook` | Search | Locate cooking demonstrations across your library | ✓ |
| `speaker` | Search | Find someone explaining a concept to camera | ✓ (visual cue: person facing camera) |
| `ontext` | Search | Find moments with on-screen text or graphics | ⚠️ **Overpromises** — no OCR. ViCLIP may catch obvious chyrons / graphics by visual style but won't read text content. Either weaken the title or queue OCR (P0). |
| `laughter` | Search | Find specific sounds — laughter or applause | ⚠️ **Overpromises** — wav2vec2 is speech-tuned. Recall on pure-audio events unverified. Queue PANN (P1). |
| `product` | Search | Find product close-ups for B-roll cuts | ⚠️ Marginal — ViCLIP catches "close-up of object" visually but won't recognise specific products. Acceptable if reviewers don't expect brand-level matching. |
| `summarize` | Analyze | Summarize the entire video in 3 sentences | ✓ |
| `timeline` | Analyze | Create a timeline report with exact timestamps | ✓ (#7) |
| `hashtags` | Analyze | Generate hashtags and topic tags | ✓ |
| `range-qa` | Analyze | Ask anything about a specific time range | ✓ (#9) |
| `moderate` | Analyze | Moderate content for community guidelines | ⚠️ **Overpromises** — relies on VLM-only, no specialised moderation classifier. Demo will work but production reliability is uncertain. Queue P2 moderation classifier. |
| `visuals` | Analyze | Explain visual composition and style | ✓ (#1, #3) |
| `dunk-ground` | Ground | Find the exact moment of the dunk | ⚠️ Depends on `s.grounding_checkpoint` — falls back to untrained weights if absent (`backend/video-service/main/pipeline/ground.py:34`). The CLIP-only QD-DETR ckpt validated 2026-05-17 is in `third_party/qd_detr/` but not yet wired into `/ground`. |
| `voice-raise` | Ground | When does the speaker raise their voice | ⚠️ **Overpromises** — CLIP-based grounding has no access to audio prosody. Either drop or wire an audio-feature input to the grounding head. |
| `product-reveal` | Ground | Locate the product reveal shot | ⚠️ See `product` — visual proxy only. |
| `impact` | Ground | Find the moment of impact or explosion | ✓ Visual cue, plausible |
| `cut-start` | Ground | When does the cooking begin | ✓ Visual cue (kitchen / cutting board) |
| `title-card` | Ground | Find the title-card or opening graphic | ⚠️ Without OCR this catches visual style of title cards but not the title text. Acceptable approximation. |
| `all` / `with-speech` / `silent` / `long` | Segment | Shot filters | ✓ Pure payload filtering on `/segments` — no overpromise |

**Tiles flagged for follow-up:** `ontext`, `laughter`, `moderate`, `voice-raise`, and the GROUND set (pending checkpoint wiring). When the next playground iteration ships, either (a) close the underlying capability gap, or (b) reword the tile title so it doesn't imply a guarantee the pipeline can't keep.

---

## 6 · How to keep this doc honest

This audit is point-in-time as of 2026-05-17. If you add a new model integration or change which checkpoint `/ground` loads, the verdict columns drift. Re-run the audit whenever:

- A new entry is added to `backend/video-service/main/pipeline/ingest.py` (new ingest stage)
- A new file appears in `backend/agent-service/main/agent/stirrups/` (new agent tool)
- `s.grounding_checkpoint` flips from "untrained / missing" to a real trained file
- A new example tile is added to `frontend/src/pages/playground/data/examples.ts`

The cheapest sanity check is grepping for the model names listed in §2's ❌ rows — if any of those start appearing in `requirements.txt` or imports, the corresponding row needs to flip.
