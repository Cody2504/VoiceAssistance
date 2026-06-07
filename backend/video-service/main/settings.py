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

    # InternVideo2 grounding (EXPERIMENTAL, behind a flag) — parallel to the
    # CG-DETR/lighthouse path. See services/iv2_grounding_service.py +
    # pipeline/ground_iv2.py. Validated standalone on a 3090; not yet wired into
    # the default Ground tile. Switch the Ground backend with this flag.
    grounding_backend: str = "lighthouse"                   # "lighthouse" | "iv2"
    iv2_device: str = "cpu"
    iv2_video_ckpt: str = "/models/iv2/video_encoder.pt"    # SG-DETR FE traced InternVideo2-1b
    iv2_text_ckpt: str = "/models/iv2/text_encoder.pt"      # InternVideo2 text tower (bert-large)
    # Trained SG-DETR head (MRDETR) — a pre-stripped PURE state-dict (no training-time
    # pickled modules), so it loads with weights_only=True and needs no sg-detr repo.
    # Produced once from sgdetr_qvhighlights_pt.ckpt: keep `model.`-prefixed tensors.
    iv2_sgdetr_head_ckpt: str = "/models/iv2/sgdetr_head_state_dict.pt"
    iv2_clip_length_sec: float = 2.0

    # Shot detection backend (ingest segment grid). "scenedetect" (PySceneDetect,
    # default) | "transnet" (TransNetV2 PyTorch). TransNetV2 gives cleaner cuts on
    # high-motion footage; falls back to PySceneDetect if weights/deps are missing.
    shot_detector: str = "scenedetect"
    transnet_weights: str = "/models/transnetv2/transnetv2-pytorch-weights.pth"

    # Hierarchical summary (Analyze tile long-context Q&A)
    summary_window_size_sec: float = 120.0                  # 2-min rolling windows
    summary_llm_model: str = "openai/gpt-4o-mini"           # via OpenRouter
    summary_max_segments_per_window: int = 8

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


@lru_cache
def get_settings() -> Settings:
    return Settings()
