"""Targeted backfill: populate jockey_visual_entities for existing videos WITHOUT a
full re-index (does not touch caption/CLIP/DINO/KG). Idempotent per video (point ids
are deterministic uuid5); resumable (skip videos already populated). Uses the local
file if present, else downloads the source from S3 by its DB minio_key. Run with
vast.env sourced (+ PYTHONPATH=backend). Optional arg: comma-separated filenames."""
import sys, os, tempfile
sys.path.insert(0, "/workspace/VoiceAssistance/backend/video-service")
sys.path.insert(0, "/workspace/VoiceAssistance/backend")
from uuid import UUID
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from cm_shared.settings import get_base_settings
from main.models.video import Video
from main.storage.minio import download_to_path
from main.api import search as S
from main.settings import get_settings
from main.encoders.visual_entities import get_visual_entity_captioner
from main.encoders.search import TextEmbedder
from main.encoders.config import config
from main.encoders.indexer import extract_frames
from main.pipeline.ingest import _upsert_visual_entities

s = get_settings(); qc = S._qdrant(); cap = get_visual_entity_captioner()
emb = TextEmbedder(api_key=config.openrouter_api_key, model=config.text_embedding_model,
                   base_url=config.openrouter_base_url)
only = set((sys.argv[1].split(",") if len(sys.argv) > 1 else []))

# DB: video_id -> minio_key (for non-local downloads)
_db = sessionmaker(create_engine(get_base_settings().sync_database_url, pool_pre_ping=True, future=True))()
minio_keys = {str(r[0]): r[1] for r in _db.execute(select(Video.id, Video.minio_key)).all()}
_db.close()

# shots from jockey_segments_text
shots_by_vid: dict = {}
off = None
while True:
    pts, off = qc.scroll("jockey_segments_text", limit=2000, offset=off, with_payload=True, with_vectors=False)
    for p in pts:
        pl = p.payload
        shots_by_vid.setdefault(pl["video_id"], []).append((pl.get("shot_idx", pl.get("idx")), pl["t_start"], pl["t_end"]))
    if off is None:
        break

names = {p.payload["video_id"]: p.payload["original_filename"] for p in
         qc.scroll("jockey_videos", limit=500, with_payload=True)[0]}
LOCAL_DIRS = ["/workspace/test_clips", "/workspace/test_clips/sports", "/workspace/test_clips/imgsearch"]
def local_path(fn):
    for d in LOCAL_DIRS:
        p = os.path.join(d, fn)
        if os.path.exists(p):
            return p
    return None

already = set()
try:
    a, _ = qc.scroll(s.visual_entities_collection, limit=20000, with_payload=True)
    already = {p.payload["video_id"] for p in a}
except Exception:
    pass

done = 0
for vid, shots in shots_by_vid.items():
    fn = names.get(vid, "")
    if only and fn not in only:
        continue
    if vid in already:
        print("skip (done):", fn, flush=True); continue
    path = local_path(fn); tmpf = None
    if not path:
        key = minio_keys.get(vid)
        if not key:
            print("SKIP (no minio_key):", fn or vid, flush=True); continue
        tmpf = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
        try:
            download_to_path(s.minio_bucket_videos, key, tmpf)
            path = tmpf
        except Exception as e:  # noqa: BLE001
            print("SKIP (download failed):", fn, e, flush=True)
            os.path.exists(tmpf) and os.remove(tmpf); continue
    try:
        shots = sorted(shots, key=lambda x: x[0])
        frame_batches = [extract_frames(path, t0, t1, max_frames=s.visual_entities_frames_per_shot)
                         for _, t0, t1 in shots]
        texts = cap.caption_batch(frame_batches)
        vecs = emb.encode_batch([t or " " for t in texts]) if any(texts) else None
        segments = [(t0, t1) for _, t0, t1 in shots]
        _upsert_visual_entities(qc, UUID(vid), texts, vecs, segments, s)
        done += 1
        print("done:", fn, "shots:", len(shots), "nonempty:", sum(1 for t in texts if t), flush=True)
    finally:
        if tmpf and os.path.exists(tmpf):
            os.remove(tmpf)
print(f"BACKFILL DONE (newly indexed {done})", flush=True)
