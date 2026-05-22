# Slice 1 — Agent E2E verification + Thinking-UI rework

**Date:** 2026-05-15
**Status:** Approved, implementation in progress
**Owner:** main session

## 1. Goals

Verify the agent's three production tools end-to-end against the running stack, and reshape the chat UI so a non-technical user can follow what the agent is doing in real time. No new agent capabilities; no payment; no billing; no moment-capture.

Success means: five named test cases pass with screenshots, and the "Agents Thinking" component renders the phase-based timeline shown in the reference mockup (Image #1) with the multi-summary card stack from Image #2.

## 2. Scope

### In

- Frontend rewrite of `frontend/src/components/chat/AgentsThinking.tsx` to render a phase-based step timeline.
- Frontend diff of `frontend/src/components/chat/VideoSummaryCard.tsx` and `ChatThread.tsx` to match the multi-summary stack layout.
- Chrome-devtools-MCP-driven test script that exercises five canonical agent flows.
- Prompt tuning under `jockey/prompts/` only when a test case fails because the planner routes incorrectly.

### Out

- Backend SSE protocol changes (`backend/agent-service/main/api/chat.py` stays as-is).
- Ad-hoc OS-file drag-and-drop upload.
- TRACE / find_moment / grounding-tool (memory-flagged decision still stands).
- VNPay payment integration.
- Token-usage cost model.
- Any new LLM call (no per-phase summarizer).

## 3. Strategy decisions (locked)

| Decision | Choice | Rationale |
|---|---|---|
| Step model | **B** — frontend phase-binning over existing events | Zero backend churn, zero extra LLM cost, label fidelity is acceptable using raw thoughts as bodies |
| Drag-drop scope | **A only** — verify existing drag-from-library | Ad-hoc upload is its own slice; competes with UI work for time |
| Visual mockup source | User-provided Images #1, #2 | No mockup generation needed |

## 4. Phase taxonomy

Four phases. The frontend bins raw SSE events (`thought`, `tool_call`, `tool_result`, `message`) into phases on the order they arrive.

| # | Phase label | Triggered by | Body |
|---|---|---|---|
| 1 | "Understanding your request" | First `thought` with `agent === "planner"` | Streamed planner thought verbatim |
| 2 | "Choosing a worker" | First `thought` after planner with `agent` ∈ {supervisor, instructor} | Streamed supervisor/instructor thought verbatim |
| 3 | `{toolLabel}` — one per `tool_call` | `tool_call` event | `args` (top) + `result` (below, once `tool_result` arrives) |
| 4 | "Composing reply" | Reflect-tagged stream begins | Streaming reply text (also appears outside the timeline as the main answer) |

`toolLabel` is a static lookup:

| Tool name | Label |
|---|---|
| `video-search` | "Searching the corpus" |
| `time-range-analysis` | "Reading transcript {t_start}–{t_end}" |
| `gist-text-generation` / `summarize-text-generation` / `free-text-generation` | "Summarizing the video" |
| (other) | tool name verbatim |

**Status rules:** the latest emitted phase is `active` (filled dot, subtle pulse). Earlier phases are `done` (hollow dot). On `end`, the active phase flips to `done`. On a `tool_result` with an error payload, that step becomes `error` (red dot).

**Phase-boundary heuristic for parallel thoughts:** if `agent` tag changes between consecutive thought deltas, start a new phase. Preserves ordering even if LangGraph interleaves planner/supervisor branches.

## 5. Components

### 5.1 `AgentsThinking.tsx` (rewrite)

Introduces a pure derivation function:

```ts
type Step =
  | { kind: "phase"; label: string; status: "active" | "done" | "error"; body?: string }
  | { kind: "tool";  label: string; status: "active" | "done" | "error"; args: unknown; result?: unknown };

function deriveSteps(thinkingSteps: ThinkingStep[]): Step[];
```

`deriveSteps` is the only piece worth unit-testing. Storage in `Message.thoughts` remains the raw `ThinkingStep[]` wire format so we can iterate the binning rules without DB migration.

Render: vertical rail on the left with status dots, label-right. Each row is a chevron-collapsible container; expanded body shows the verbatim body (thought text, or tool args+result block).

### 5.2 `VideoSummaryCard.tsx` + multi-summary stack

Diff existing component against Image #2 during implementation. Expected gaps: spacing between cards, divider treatment, alignment of the attached-chip rail above the composer. No new component anticipated.

### 5.3 `ChatThread.tsx`

Two small changes:
- `extractClips` / `extractSummary` are likely to break against the new TRACE-free `tool_result` shape — first failing test will tell us what keys the payload actually uses; adjust extractors.
- Replace the inline divider class with the design-matched divider.

## 6. Test plan (chrome-devtools-driven)

All tests run against the local dev stack (frontend dev server + backend docker compose). Each test produces a screenshot saved under `docs/superpowers/test-runs/2026-05-15/<n>-<slug>.png`.

| # | Input | Expected agent path | UI assertion |
|---|---|---|---|
| 1 | "Fetch me 3 clips about tennis" | planner → supervisor → `video-search(query="tennis", k=3)` → reflect | 4 phases; clip results render; 3 video tiles |
| 2 | Attach 3 indexed videos + "Summarize each of these" | planner → supervisor → 3× `summarize-text-generation` → reflect | 5+ phases; 3 `VideoSummaryCard`s stacked; chip rail visible (Image #2 match) |
| 3 | Attach 1 video + "From 0:15 to 0:25 what does the tutor talk about?" | planner → supervisor → `time-range-analysis(start=15, end=25)` → reflect | Phase 3 label reads "Reading transcript 0:15–0:25"; reply quotes/paraphrases transcript |
| 4 | "Find the video that talks about a math problem" | planner → supervisor → `video-search(query="math problem")` → reflect | ≥1 clip returned; thumbnail + caption |
| 5 | Drag an indexed library video into the composer, then "Tell me the main event" | attachment chip → planner → supervisor → `summarize-text-generation` → reflect | Chip rendered before send; summary card after |

Failure of a test routes to: prompt tuning under `jockey/prompts/`. No new tools, no new code paths.

## 7. Risks

1. **Interleaved agent thoughts** breaking the phase-binning. Mitigation: phase-boundary heuristic in §4.
2. **`tool_result` shape drift** from the TRACE removal — `extractClips` / `extractSummary` may key off fields that no longer exist. Mitigation: capture raw payloads from test 1 and test 5 first; adjust extractors before declaring those tests pass.
3. **Time-range parsing reliability** — does the planner reliably emit `(15.0, 25.0)` from "0:15 to 0:25"? Mitigation: if test 3 fails on tool args rather than tool result, fix `jockey/prompts/video_text_generation.md`.

## 8. What this slice does NOT change

- `backend/agent-service/main/api/chat.py` SSE event protocol.
- `backend/agent-service/main/agent/jockey_graph.py`.
- `jockey/jockey_graph.py` and stirrups (no new tools).
- Backend services: `iam`, `video-service`, `token-usage`, `gateway` — untouched.
- Database schemas — no migration.

## 9. Open follow-ups (for later slices, not this one)

- VNPay sandbox + token-cost model — background research subagent running; output expected at `docs/superpowers/research/2026-05-15-vnpay-and-token-cost-notes.md`. Fold into a follow-up slice spec when received.
- Ad-hoc OS-file upload into chat (deferred from this slice).
- Moment-capture / find_moment — only if user revisits the memory-flagged decision.

## 10. Definition of done

- All five test cases pass with screenshots committed under `docs/superpowers/test-runs/2026-05-15/`.
- `AgentsThinking.tsx` renders the phase timeline matching Image #1 (visually verified via chrome-devtools).
- Multi-summary stack matches Image #2.
- No backend file modified other than (optionally) prompt files under `jockey/prompts/`.
- `git status` for this slice shows changes only under `frontend/src/components/chat/`, `docs/superpowers/`, and optionally `jockey/prompts/`.

## 11. Results (2026-05-15 session)

| # | Test | UI verdict | Backend notes |
|---|---|---|---|
| 1 | "Fetch me 3 clips about tennis" | ✅ Pass — 3 phases (Understanding → Searching the corpus → Composing reply), 3 clip tiles, friendly reply | Corpus search worked once new endpoint + tool were in place |
| 2 | Attach 2 indexed videos + "Summarize each of these" | ✅ Pass — 4 phases, 2 `VideoSummaryCard`s stacked (matches Image #2), chip rail visible | Two parallel `ask_video_local` calls, both succeeded |
| 3 | "From 0:15 to 0:25 what does the tutor talk about?" (SAT table) | ✅ Pass on label + routing — phase reads "Reading transcript 0:15–0:25"; agent passed `t_start=15, t_end=25` correctly | Backend Qwen3-VL got frames only; reply says "no transcript available". Whisper-content surfacing in `analyze_range` is a separate backend gap, not slice 1 |
| 4 | "Find the video that talks about a math problem" | ✅ Pass — corpus search returned shots, agent named SAT table.mp4 as the math-problem candidate | Retrieval ranking is weak (text↔visual embedding alignment imperfect, scores near zero) — separate retrieval-quality concern |
| 5 | Drag tennis.mp4 from library → "Tell me the main event" | ✅ Pass — chip rendered before send, `Summarizing the video` phase, summary card after | `ask_video_local(video_id, "main event")` completed cleanly |

### Scope creep absorbed (vs. original spec §2 "Out of scope")

The original spec said *"no backend SSE protocol change, no new tools"*. Reality required these additions because the original agent tools were per-video-only — corpus-wide search didn't exist at all:

- **New endpoint** `POST /api/v1/videos/search` in `backend/video-service/main/api/search.py` (user-scoped, no `video_id` in path).
- **New agent tool** `search_corpus(query, top_n, group_by)` in `backend/agent-service/main/agent/stirrups/video_search.py`.
- **Pre-existing bug fixed** in `_embed_query` (called non-existent `embed_text` instead of `ViCLIPEmbedder.encode_text`). Same bug would have broken the per-video search if it had ever been smoke-tested.
- **Response-envelope unwrap** in agent stirrups so the frontend `extractClips` / `extractSummary` find `result.shots` / `result.answer` directly (not nested under `result.data`).
- **`toolLabel` extended** in `AgentsThinking.tsx` to map the new agent-service tool names (`search_corpus`, `search_video_local`, `ask_video_local`) to friendly labels.
- **Prompts rewritten** in `backend/agent-service/main/prompts/{planner,instructor,video_search,video_editing}.md` to drop the legacy "Index ID" concept (TwelveLabs-era language that survived the TRACE migration). The user shouldn't be asked for an Index ID; the system scopes by `user_id` from JWT.

User explicitly authorized this expansion mid-session after seeing the gap.

### Known gaps to address in follow-up slices

1. **Whisper transcript not surfaced in time-range Q&A.** `video-service/qa.py:analyze_range` samples frames only. Need to add ASR text from the time window into the Qwen3-VL prompt.
2. **Corpus retrieval ranking quality.** ViCLIP-text query × ViCLIP-visual shot embeddings aren't well-aligned out of the box; scores cluster near zero. Either reproject queries through a finetuned head or switch to a CLIP-aligned text encoder.
3. **`_embedder` is a process-singleton in video-service** — fine for now; if we move to multi-worker uvicorn, the load happens per-worker (~60s CPU cold start). Tolerable for v1.
4. **VNPay sandbox + token-cost model** — research notes saved at `docs/superpowers/research/2026-05-15-vnpay-and-token-cost-notes.md`. Fold into a follow-up payment+billing spec.
5. **Ad-hoc OS-file upload from chat** (deferred per original spec §2).
6. **Moment-capture / find_moment** — memory-flagged decision unchanged; not revisited this session.

## 12. Index audit (post-slice review)

User reviewed test screenshots and flagged: tennis "Clip 2" time range nonsensical (24.26–24.32s = 60ms tail of a 24s video), and SAT table.mp4 showing up for "tennis" queries.

Dumped indexed Qdrant payloads to `docs/superpowers/debug/2026-05-15-indexed-shots.json`. Findings:

- **Total points in `jockey_shots`: 3.** Two videos × shot count = 2 + 1.
- **`tennis.mp4`** (24.3s, status=ready): 2 shots, but shot 1 is a 67ms numerical-precision residual (24.2576→24.3243). `asr_text` empty for both.
- **`SAT table.mp4`** (79.1s, status=ready): **1 shot** covering the entire video. Scene detector failed to segment. `asr_text` empty.
- **Two `status=error` videos** (older uploads): point-ID format bug at upload time ("`{video_id}:{idx}` is not a valid point ID, valid values are unsigned int or UUID"). Was fixed downstream to use uuid5, but these rows still poison the library view.

### Root causes

1. **Shot detector thresholds too lax** — see `backend/video-service/main/pipeline/ingest.py`. Either PySceneDetect threshold needs tuning or fallback chunking (e.g., fixed 5s windows) needed when no scene cuts detected.
2. **Whisper not running, or running silently null** — all `asr_text` are empty strings. Either the ingest pipeline doesn't actually invoke Whisper, or it does and the result is dropped. Need to verify.
3. **Retrieval ranking is meaningless** with 3 total points — any query returns all of them in some order. This will only manifest as a real ranking once 50+ shots are in the index.

### What I shipped in response (alongside the audit)

- **Reply suppression in `ChatThread.tsx`** — the long "Clip 1: … Clip 2: …" enumeration the reflect LLM was writing is now hidden whenever clip tiles or summary cards already show the content. Matches user's Image #5 / Image #6 intent. Screenshot at `docs/superpowers/test-runs/2026-05-15/06-reply-suppression-after.png`.
- **Audit JSON** saved for the user to inspect alongside the screenshots.

### Follow-ups for next slice

1. **Fix shot detection** — produce ≥1 shot per 10–15s of video. SAT table (79s, multi-scene tutorial) should yield ≥5 shots.
2. **Fix or remove Whisper integration** — `asr_text` columns are dead weight if empty everywhere; either wire Whisper through to populate, or drop the column. Probably wire it through, since Test 3's time-range Q&A needs transcript content to be useful.
3. **Clean up `status=error` videos** — either auto-purge old failed rows or gate them out of the library list query (`WHERE status != 'error' OR error_age < 7d`).
4. **Score-threshold the corpus search** — currently `Qdrant.search()` returns top-N regardless of similarity score. Add a minimum score (e.g., 0.2 cosine) to drop unrelated bleed-through.
5. **Optional: short ack reflect prompt** — when tiles/cards are shown the LLM reply is hidden, so the wasted reflect LLM call is just a cost. Override `_reflect_node` in `JockeyLocal` to no-op when a tool just produced renderable output, or to emit a single sentence. Cost-only concern, not user-visible.

## 13. Indexing pipeline fix (2026-05-15 follow-up)

The audit in §12 surfaced shot-detection collapse + empty Whisper. Root-causing showed **four** real bugs in the indexer, fixed in this session:

1. **`detect_shots()` in `jockey/open_source/indexer.py`** — PySceneDetect threshold=27 silently returns one giant shot for static videos. Added `max_shot_s=10` post-processing that subdivides any shot longer than 10s into equal windows, plus `min_shot_s=0.75` that merges trailing residuals (the 67ms tail). Result: SAT table.mp4 went from 1→8 shots, tennis.mp4 from 2→3 cleanly.
2. **`transcribe_segment` did not exist** in `jockey/open_source/asr_whisper.py` — `ingest.py` imported a top-level convenience function that was never written, only the `WhisperASR` class existed. Added a singleton-backed `transcribe_segment(video_path, start_sec, end_sec)`. Result: every shot now has real ASR text (Whisper-base on CPU, with the existing RMS-silence guard).
3. **Encoder API mismatches** in `ingest.py` — three classes were called with wrong method names: `ViCLIPEmbedder.embed_clip` (doesn't exist; right call is `extract_frames` + `encode_video_batch`), `AudioEncoder.embed_segment` (right name is `encode_audio(video_path, start_sec=, end_sec=)`), and `MetadataEncoder()` (signature requires a `text_embedder` arg; MetadataEncoder was the wrong class entirely — per-shot caption embeddings belong to `TextEmbedder` from `jockey/open_source/search.py`).
4. **Pre-existing dead-row poison** — two `status="error"` rows in `videos` from a Qdrant point-ID format bug fixed long ago. Still showing up in the library tiles. Followup §12.3 — cleanup, not in this patch.

### Verification

`docs/superpowers/debug/2026-05-15-indexed-shots-final.json` shows the post-fix state:
- 11 total points in `jockey_shots` (3 tennis + 8 SAT), all with real ASR text.
- "tennis" query (live, via `POST /api/v1/videos/search`) returns **only tennis.mp4 shots** with cosine scores 0.22-0.25.
- "math problem with fractions" returns SAT (0.20) above tennis (0.14).
- "probability fractions" returns all 3 top shots from SAT.

Browser end-to-end: `docs/superpowers/test-runs/2026-05-15/07-tennis-after-indexing-fix.png` — 3 properly-bounded 8s tennis clips, no SAT bleed, no redundant text reply. Matches Image #6 layout.

### Scripts added

- `backend/video-service/main/scripts/dump_index.py` — dumps Qdrant payloads + DB rows to JSON for inspection.
- `backend/video-service/main/scripts/reindex.py` — clears Qdrant shots per video and re-runs `run_indexing()` in-process (worker container).

Both kept under `main/scripts/` for re-use after further indexer changes.

## 14. Browser-reachable thumbnails + video playback (2026-05-15)

User reported library tiles showed only placeholder text ("video", "ERROR") and asked for the Image #8 grid layout (real thumbnails + click-to-play). Two real wiring bugs:

1. **MinIO presigned URLs were signed against `http://minio:9000`** (the internal docker hostname). Browser must hit `http://localhost:9000` (the host port mapping), and SigV4 signs the `Host` header — so the same URL fails with 403 when the host differs from what was signed. **Fix:** added `minio_public_endpoint = "http://localhost:9000"` to `video-service/main/settings.py` and a separate `_s3_public()` boto3 client in `storage/minio.py`. `presigned_get()` now signs against the public endpoint so the URL works as-is from the browser.

2. **`<img src>` cannot carry the Bearer token**, so the old 307-redirect thumb endpoint failed with 401 before the redirect could fire. **Fix:** changed `GET /videos/{id}/thumb/{shot_idx}` to return `success_response({"url": presigned})` (symmetric with `/stream`). Frontend `VideoThumb` now resolves the URL via authed `axios.get()` and points `<img src>` at the presigned MinIO URL directly. Library tiles default to `shot_idx=0` as the cover thumbnail.

### Verification

- `GET /thumb/0` returns 200 + `image/jpeg` (3960 bytes for tennis.mp4).
- `GET /stream` returns 206 + `video/mp4` on a Range request.
- Browser screenshot `docs/superpowers/test-runs/2026-05-15/08-library-thumbs-after-wire.png` — tennis tile shows the actual court, SAT tile shows the actual contingency-table problem.
- Browser screenshot `docs/superpowers/test-runs/2026-05-15/09-video-playback-modal.png` — clicking a tile opens `VideoPreviewModal` and the `<video>` plays the MP4 inline (verified via `evaluate_script`: `currentTime=18.38s, paused=false, readyState=4, duration=79.18s, error=null`).

### S3 bucket note

The user added AWS S3 creds for the `jockeyassistant` bucket (`ap-southeast-2`) in `.env`. These are wired to the existing `scripts/s3_*.py` smoke tests and `frontend/src/pages/s3-test/S3TestPage.tsx` — a separate test surface, not a replacement for MinIO. The production video pipeline still uses MinIO. Migrating storage from MinIO to S3 is a follow-up, not part of this fix.

## 15. Public-vs-internal presigned URLs + Whisper transcript in QA (2026-05-15)

Re-running the 5-case sweep after the thumb wire-up surfaced two more bugs that needed fixing for the agent tools to work end-to-end:

1. **Presigned URLs broke in-container consumers** — the `_s3_public()` change made every URL point at `localhost:9000`. The Qwen3-VL client lives inside the `jockey-video` container, where `localhost` is the container itself, not the host. Result: Qwen3-VL fetched zero bytes and replied "blank black image" to every summarize request. **Fix:** `presigned_get(..., public: bool = True)`. The thumb + stream endpoints (browser-facing) use the default `public=True`; the QA endpoint (in-container) passes `public=False` to get the `minio:9000` URL.

2. **Whisper text was indexed but never reached the QA model** — Test 3 ("From 0:15 to 0:25 what does the tutor talk about?") had been routing correctly all along, but the QA endpoint only fed Qwen3-VL the visual frames. The transcripts were sitting in the Qdrant payload doing nothing. **Fix:** added `_fetch_transcript_window(video_id, t_start, t_end)` to `video-service/main/api/qa.py` that scrolls Qdrant for shots overlapping the requested window, concatenates their `asr_text`, and prepends the result to the prompt with framing instructions ("Use both the visual frames AND the transcript above to answer. If the answer is in the transcript, quote or paraphrase it directly."). After the fix, the agent's reply for Test 3 is a direct paraphrase of the SAT tutor's actual words: *"The speaker says: 'So of the customers who bought scoops, so I can do that as the denominator of a fraction.'"*

### Final test sweep — all 5 pass

| # | Test | Result | Screenshot |
|---|---|---|---|
| 1 | "Fetch me 3 clips about tennis" | ✅ 3 tennis tiles, no SAT bleed, real thumbnails, no redundant text | `final-01-tennis.png` |
| 2 | Attach SAT + tennis + "Summarize each of these videos" | ✅ Both summary cards rendered (probability problem + tennis serve), real thumbnails, no chat enumeration | `final-02-summarize-both.png` |
| 3 | "From 0:15 to 0:25, what does the tutor talk about?" | ✅ Phase label "Reading transcript 0:15–0:25", reply quotes actual transcript: *"So of the customers who bought scoops, so I can do that as the denominator of a fraction."* | `final-03-time-range-with-transcript.png` |
| 4 | "Find the video that talks about a math problem" | ✅ 3 SAT clips, no tennis bleed, all 0:09 cleanly bounded windows | `final-04-math-problem.png` |
| 5 | Drag tennis + "Tell me the main event from this video" | ✅ Summary card with full description of the serve, real thumbnail, GABE JARAMILLO branding identified | `final-05-tennis-main-event.png` |

All five user-listed agent use cases now work end-to-end.

## 16. Polish round: parent-video presentation + "video" not "images" phrasing

Two issues surfaced in the post-test review (Image #9):

1. **"Find the video that talks about a math problem" returned 3 same-video clips.** The LLM kept calling `search_corpus(group_by="clip")` despite prompt updates pushing it toward `"video"` for singular queries. Even after strengthening the inline `SEARCH_PROMPT`, gpt-4o-mini still picked clip mode.
2. **Replies say "Based on the provided images".** Qwen3-VL's default phrasing for a frame batch — accurate to its mechanism, wrong UX for a "video understanding" product.

### Fixes

- **Pipe `group_by` through to the frontend as a presentation hint.** `search_corpus` response already carried `group_by` at the top level; corpus search now also includes `video_duration_s` per shot. `ChatThread.extractClips` reads `group_by` and sets `display_mode: "parent_video" | "clip"` on each `ClipResult`.
- **Frontend dedupe fallback.** When the LLM picks `"clip"` but every returned shot is from the same `video_id`, the frontend collapses to one parent-video tile (the LLM probably should have picked `"video"`; this catches the mistake). `ChatThread.tsx:extractClips`.
- **Render parent vs clip tiles differently.** `VideoSearchResults`: parent_video tiles show the full video duration in the badge, the original filename below the tile, and click plays from `t=0`. Clip tiles keep the existing behavior (shot window badge, click plays from `t_start`).
- **Phrasing directive in QA prompt.** Appended to every `qa.py` prompt: *"Phrasing: refer to what you're analyzing as 'the video' or 'this clip', never 'the images', 'the frames', 'the pictures', or 'the provided images'. Do not mention that you are seeing a sequence of frames; talk about the action and content."* Verified: reply for "Tell me the main event from this video" now opens with *"This clip captures..."*, not "Based on the provided images".
- **Tightened `SEARCH_PROMPT` + `instructor.md`** to map user phrasing to tool args more explicitly (singular → `group_by="video", top_n=1`; plural-no-count → `group_by="video", top_n=3`; "fetch N clips/moments/scenes" → `group_by="clip", top_n=N`). This is best-effort prompt tuning — the frontend fallback is the safety net.

### Verification

- `final-04b-math-parent-video.png` — "Find the video..." → ONE tile (1:19, "SAT table.mp4").
- `final-05b-phrasing-fix.png` — "Tell me the main event from this video" → "This clip captures a young tennis player executing a serve on an outdoor court..."
