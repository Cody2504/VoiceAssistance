from functools import lru_cache

from cm_shared.settings import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = "video-service"
    service_port: int = 1101

    # Qdrant
    qdrant_host: str = "qdrant"
    qdrant_port: int = 6333
    qdrant_collection: str = "jockey_shots"

    # MinIO / S3
    minio_endpoint: str = "http://minio:9000"
    # Publicly-reachable endpoint used when generating presigned URLs for the browser.
    # Containers talk to MinIO via `minio:9000`; the browser cannot resolve that hostname
    # and must hit the port mapping on the host instead.
    minio_public_endpoint: str = "http://localhost:9000"
    minio_root_user: str = "jockey"
    minio_root_password: str = "jockey_dev_secret"
    # SigV4 region. Local MinIO ignores it; real AWS S3 requires it to match the
    # bucket's region or presigned URLs 403. Override via MINIO_REGION on the pod.
    minio_region: str = "us-east-1"
    minio_bucket_videos: str = "videos"
    minio_bucket_edits: str = "edits"
    minio_bucket_thumbs: str = "thumbs"

    # Lighthouse (CG-DETR visual MR + QD-DETR CLAP audio MR).
    # Checkpoints are downloaded from the official lighthouse release; see
    # backend/video-service/scripts/download_lighthouse_weights.sh.
    lighthouse_device: str = "cpu"
    lighthouse_cg_detr_ckpt: str = "/models/lighthouse/clip_slowfast_cg_detr_qvhighlight.ckpt"
    lighthouse_clap_qd_detr_ckpt: str = "/models/lighthouse/clap_qd_detr_clotho_moment.ckpt"
    lighthouse_slowfast_ckpt: str = "/models/lighthouse/SLOWFAST_8x8_R50.pkl"
    lighthouse_pann_ckpt: str = "/models/lighthouse/Cnn14_mAP=0.431.pth"
    lighthouse_visual_feature_name: str = "clip_slowfast"   # "clip" to skip SlowFast on CPU-only setups
    lighthouse_audio_feature_name: str = "clap"
    lighthouse_clip_length_sec: float = 2.0                 # 75 clips × 2s = 150s window
    lighthouse_max_window_sec: float = 150.0
    lighthouse_window_overlap_ratio: float = 0.5            # for highlight sliding scan
    lighthouse_highlight_query: str = "an interesting key moment or highlight from the video"

    # Grounding backend for Ground + Highlights. PROD default: InternVideo2 + the
    # trained SG-DETR head (services/iv2_grounding_service.py + pipeline/ground_iv2.py).
    # "lighthouse" selects the older CG-DETR(visual)/QD-DETR(audio) fallback
    # (services/lighthouse_service.py + pipeline/ground_v2.py). Override with the
    # GROUNDING_BACKEND env var.
    grounding_backend: str = "iv2"                          # "iv2" | "lighthouse"
    iv2_device: str = "cpu"
    iv2_video_ckpt: str = "/models/iv2/video_encoder.pt"    # SG-DETR FE traced InternVideo2-1b
    iv2_text_ckpt: str = "/models/iv2/text_encoder.pt"      # InternVideo2 text tower (bert-large)
    # Trained SG-DETR head (MRDETR) — a pre-stripped PURE state-dict (no training-time
    # pickled modules), so it loads with weights_only=True and needs no sg-detr repo.
    # Produced once from sgdetr_qvhighlights_pt.ckpt: keep `model.`-prefixed tensors.
    iv2_sgdetr_head_ckpt: str = "/models/iv2/sgdetr_head_state_dict.pt"
    iv2_clip_length_sec: float = 2.0

    # VLM action re-caption (roadmap #3): eager per-segment timestamped
    # action captions, surfaced as the `vlm_actions` timeline track.
    vlm_actions_enabled: bool = True           # build action captions at ingest
    vlm_actions_fps: float = 1.0               # frame sampling rate per segment
    vlm_actions_max_frames: int = 32           # hard cap on frames sent to the VLM per segment
    vlm_actions_event_span_sec: float = 2.0    # synthetic event length around each action timestamp
    # Concurrency for the per-segment action-caption VLM calls (one OpenRouter
    # request per segment). Bounded to stay under OpenRouter rate limits; calls
    # also retry with exponential backoff on 429. 8 ≈ ~60 req/min at ~8s/call.
    vlm_actions_concurrency: int = 8

    # Standing event timeline + "when does X happen" fan-out (Plan 1/2/3)
    timeline_enabled: bool = True                           # build the timeline at ingest
    timeline_events_collection: str = "jockey_timeline_events"
    timeline_default_tracks: tuple[str, ...] = (
        "audio_events",
        "on_screen_text",
        "shots",
        "spoken_topics",
        "highlights",
        "vlm_actions",
        "speakers",
    )
    timeline_audio_event_min_score: float = 0.15           # min PANN score to count an audio event
    timeline_highlights_top_k: int = 8                     # DETR highlight events per video
    when_top_n: int = 10                                   # results returned by the "when" endpoint (Plan 2)
    when_refine_default: bool = True                       # run DETR refine on moment-like queries (Plan 2)

    # Audio-event vector index (roadmap #2): CLAP per-segment embeddings,
    # text-queryable ("crowd cheer", whistle, music).
    audio_events_enabled: bool = True
    audio_events_collection: str = "jockey_audio_events"

    # Speaker diarization (research F): pyannote speaker turns surfaced as
    # the `speakers` timeline track ("who said X, when"). Model is HF-gated —
    # needs HF_TOKEN with the pyannote terms accepted.
    diarization_enabled: bool = True
    diarization_model: str = "pyannote/speaker-diarization-3.1"

    # Query-time object verification (research B): GroundingDINO re-ranks
    # the top `when` candidates by open-vocab detection confidence for the
    # query's object phrase. No ingest/index cost; GPU per verified query.
    object_verify_enabled: bool = True
    object_verify_model: str = "IDEA-Research/grounding-dino-base"
    object_verify_top_k: int = 5               # candidates to verify per query
    object_verify_frames: int = 3              # frames sampled per candidate window
    # 0.35 = the official GroundingDINO repo default. Lower thresholds let the
    # model hallucinate ~0.4-0.8 boxes on phrase-less frames (verified on-pod),
    # which compresses the verify/demote gap; at 0.35 a true miss scores 0.0.
    object_verify_box_threshold: float = 0.35  # min box confidence to count a detection
    object_verify_boost: float = 0.5           # score multiplier slope on detection conf
    object_verify_demote: float = 0.6          # floor multiplier when nothing is detected

    # Motion retrieval stream (research A): real ViCLIP (temporal) per-segment
    # video embeddings → `jockey_motion`, queried by the ViCLIP text tower as a
    # `motion` fan-out stream + the corpus /search/motion endpoint.
    motion_enabled: bool = True
    motion_collection: str = "jockey_motion"
    # NB: HF repo OpenGVLab/ViCLIP is gated (auto-approve) and names the file
    # ViCLIP-L_InternVid-FLT-10M.pth — not the ViClip-InternVid-10M-FLT.pth the
    # upstream code defaults to.
    motion_weights: str = "/models/viclip/ViCLIP-L_InternVid-FLT-10M.pth"
    motion_frames_per_segment: int = 8
    motion_embedding_dim: int = 768

    # Ingest sampling knob (roadmap #7): frames sampled per segment for the
    # visual (CLIP-L) + caption encoders. More frames = better small-object
    # / short-action coverage in the visual embedding, at GPU cost.
    clipl_frames_per_segment: int = 8

    # Image multi-crop / tiling (roadmap #6): embed grid crops of index
    # frames + the query image in CLIP-L for better small-object / logo recall.
    image_tiling_enabled: bool = False
    image_tile_grid: int = 2

    # Shot detection backend (ingest segment grid). PROD default: "transnet"
    # (TransNetV2 PyTorch — cleaner cuts on high-motion footage; falls back to
    # PySceneDetect if weights/deps are missing). "scenedetect" forces PySceneDetect.
    shot_detector: str = "transnet"
    transnet_weights: str = "/models/transnetv2/transnetv2-pytorch-weights.pth"

    # Holistic segmenter core (Segment Builder). One LLM pass over the
    # caption/ASR/OCR timeline emits coherent segments + all fields.
    segment_holistic_model: str = "openai/gpt-4o-mini"   # via OpenRouter
    # Phase-2 per-segment vision refine for visual presets (off by default; the
    # core fills fields from the text timeline, this overwrites the visual ones
    # from sampled frames via the VLM for pixel-grounded accuracy).
    segment_vision_refine: bool = False
    segment_vision_frames: int = 3                       # frames sampled per segment
    segment_vision_model: str = "qwen/qwen3-vl-8b-instruct"  # OpenRouter VLM

    # Adaptive fine-grained segment grid (replaces the fixed 30s grid).
    # seg_len = max(segment_target_len_sec, duration / segment_max_count): short
    # videos get ~target-second clips; long lectures auto-coarsen so the segment
    # count (and per-segment caption cost) stays bounded. Boundaries snap to a
    # TransNet cut within ±segment_snap_tolerance_sec.
    segment_target_len_sec: float = 7.0
    segment_max_count: int = 50
    segment_snap_tolerance_sec: float = 2.0

    # DINOv2 instance-embedding channel for image search. Self-supervised
    # (no text guidance) → captures instance-level detail CLIP's category vector
    # misses. Populated per-segment at ingest into `dino_collection`.
    dino_enabled: bool = True
    dino_collection: str = "jockey_dino"
    dino_model: str = "facebook/dinov2-large"
    dino_device: str = ""  # "" → auto (cuda if available else cpu)

    # Image-search fusion / verification. CLIP + DINOv2 + OCR ranked lists
    # are fused by Reciprocal Rank Fusion; the VLM verifier then re-ranks.
    image_verify_rerank: bool = True
    image_search_rrf_k: int = 60

    # Corpus TEXT search relevance floor (CLIP-L text→video cosine). Calibrated
    # 2026-06-23: real matches top ~0.28-0.30, no-match noise tops ~0.19-0.21;
    # 0.24 sits in the empty gap → a no-match query returns [].
    corpus_search_min_score: float = 0.24
    # text-RAG (jockey_segments_text, text-embedding-3-large) cosine floor for the
    # corpus /search/text endpoint. Higher scale than CLIP-L visual; ~0.3 lets a
    # no-match query return [] while passing genuine transcript/OCR matches (~0.4+).
    corpus_text_min_score: float = 0.3

    # Hierarchical summary (Analyze tile long-context Q&A)
    summary_window_size_sec: float = 120.0                  # 2-min rolling windows
    summary_llm_model: str = "openai/gpt-4o-mini"           # via OpenRouter
    summary_max_segments_per_window: int = 24

    # Analyze prompt: how many segments to retrieve for inline grounding citations
    analyze_top_k_segments: int = 10
    analyze_token_budget: int = 100_000

    # Ground tile coarse-then-fine
    ground_top_k_candidates: int = 5
    ground_top_n_moments: int = 10
    ground_window_pad_sec: float = 15.0
    ground_iou_dedup_threshold: float = 0.5

    # OpenRouter (used by video_qa + text-embedding caller + summarizer)
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openai_api_key: str = ""

    # Phase 2a: Knowledge graph extraction (per-window entity + relation pull).
    # Off by default — flip on per-deployment once the LLM cost / latency budget
    # is reviewed. Only runs for videos that belong to an Index; videos without
    # an index_id skip the step regardless of this flag.
    kg_enabled: bool = False
    kg_qdrant_collection: str = "jockey_entities"
    # General-purpose entity types — broad enough to cover lectures, vlogs, news,
    # tutorials, documentaries, and most other instructional / spoken video.
    # Order matters: the LLM tends to prefer earlier types when a string would
    # fit two categories, so the more-information-dense lecture types come
    # first. A future per-Index override (column on `indexes` table) can let a
    # course be re-tuned to a narrower list like ("concept", "method",
    # "formula") if precision matters more than coverage.
    kg_entity_types: tuple[str, ...] = (
        "concept",      # ideas, topics, theories, principles
        "method",       # techniques, algorithms, procedures, how-tos
        "person",       # speakers, professors, characters, public figures
        "organization", # companies, schools, teams, agencies
        "tool",         # software, frameworks, hardware, instruments
        "event",        # historical events, episodes, occurrences
        "location",     # places, settings, geographies
        "object",       # physical things shown on screen
    )
    # Cosine-similarity threshold for canonicalising a freshly-extracted entity
    # against existing entities in the same index. Lower = more aggressive
    # merging; higher = more entities but less risk of collapsing distinct ideas.
    kg_canonical_sim_threshold: float = 0.85

    # Content-moderation guardrail (UC #14 enforcement). Off by default — flip on
    # per-deployment once the violence checkpoint is validated. When enabled, a
    # video whose per-category max score crosses the threshold is QUARANTINED:
    # status='flagged', skipped from the Qdrant upsert (never searchable), and
    # surfaced for admin review. Fail-open: a classifier that won't load scores 0.
    moderation_guardrail_enabled: bool = False
    moderation_violence_enabled: bool = True   # the only NEW model; gates the violence stage
    # HF image classifier (validated on pod 2026-06-27: weights load clean, real
    # Violence/NonViolence labels). Swap via env; the encoder discovers the positive
    # label from id2label. NOTE: jaranohaal/vit-base-violence-detection is BROKEN
    # (timm-format checkpoint → HF loads random weights), do not use.
    moderation_violence_model: str = "Tite2/violence-detection"
    moderation_nsfw_threshold: float = 0.85
    moderation_violence_threshold: float = 0.80
    moderation_toxic_threshold: float = 0.90
    moderation_min_flagged_segments: int = 1   # segments a category must exceed to count

    # Region/object image-search (MVP): GroundingDINO class-agnostic region
    # proposals per segment mid-frame → DINOv2 region embeddings → jockey_regions.
    # Background-invariant object/logo matching (region↔region) — fixes "clean logo
    # on white matches by background". Fused with the OCR stream (wordmark logos).
    # Off by default; needs a re-index to populate. Reuses the GroundingDINO weights
    # already pulled for object_verify and the DINOv2 weights for image search.
    region_search_enabled: bool = False
    regions_collection: str = "jockey_regions"
    region_detect_model: str = "IDEA-Research/grounding-dino-base"
    region_detect_box_threshold: float = 0.22
    region_detect_prompt: str = (
        "a logo. a sign. an advertisement. a banner. a product. a box. a bottle. "
        "a can. a package. a cup. a person."
    )
    regions_per_frame: int = 8

    # Gated Stage-2 LightGlue verifier (image search): re-ranks the fused candidate
    # shots by DISK+LightGlue+RANSAC inlier count against each candidate's keyframe
    # thumbnail. Gated — only reorders when a candidate clears `min_inliers` (a clean
    # instance match scores ~150 vs <=10 noise), so a variant-mismatch query keeps the
    # fused order. No re-index (uses cached thumbnails). Needs kornia in the env.
    lightglue_verify_enabled: bool = False
    lightglue_verify_min_inliers: int = 30
    lightglue_verify_top_k: int = 20

    # Visual-entities image search (Approach A): a 32B VLM describes each shot's
    # frames into a searchable `visual_entities` text (new jockey_visual_entities
    # collection); the query image is described by the same model. Isolated from
    # the shared caption/summaries/KG — uses its OWN model, not VLM_MODEL.
    visual_entities_enabled: bool = False           # ingest/backfill writes the field
    visual_entities_search_enabled: bool = False    # /search/image uses it as primary
    visual_entities_model: str = "qwen/qwen3-vl-32b-instruct"
    visual_entities_collection: str = "jockey_visual_entities"
    visual_entities_frames_per_shot: int = 4        # frames sampled per shot for the VLM
    visual_entities_keyword_boost: float = 0.15     # added to semantic score on token hit


@lru_cache
def get_settings() -> Settings:
    return Settings()
