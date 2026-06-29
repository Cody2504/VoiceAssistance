import os
import shutil
import subprocess
import tempfile
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from cm_shared.auth import TokenPayload, require_user
from cm_shared.db import get_session
from cm_shared.queue import VIDEO_INDEX_QUEUE, get_queue
from cm_shared.response import success_response
from cm_shared.schemas import VideoOut
from main.models.index import Index, IndexVideo
from main.models.video import IndexingJob, Video
from main.settings import get_settings
from main.storage.minio import presigned_get, s3

router = APIRouter(prefix="/api/v1/videos", tags=["videos"])


_VIDEO_EXTS = (".mp4", ".mov", ".mkv", ".webm")
_AUDIO_EXTS = (".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac")


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def upload_video(
    file: UploadFile = File(...),
    payload: TokenPayload = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    s = get_settings()
    filename = (file.filename or "").lower()
    ext = next((e for e in _VIDEO_EXTS + _AUDIO_EXTS if filename.endswith(e)), None)
    if ext is None:
        raise HTTPException(
            400,
            f"Unsupported file extension (allowed video: {','.join(_VIDEO_EXTS)}; "
            f"audio: {','.join(_AUDIO_EXTS)})",
        )

    video_id = uuid4()
    user_id = UUID(payload.sub)
    # Keep the original extension so downstream ffprobe / decoders pick the
    # right container — using `.mp4` for an `.mp3` upload would confuse them.
    key = f"{user_id}/{video_id}{ext}"
    is_video = ext in _VIDEO_EXTS

    # STEP 1 (upload): buffer to a temp file so we can capture size + duration and
    # grab a poster frame *now* — the Assets row is fully populated the instant
    # this returns, independent of the (async) indexing pass which only drives
    # `status`. Mirrors the /chunked path's local-buffer approach.
    workdir = tempfile.mkdtemp(prefix="upload_")
    local = os.path.join(workdir, f"src{ext}")
    try:
        with open(local, "wb") as fh:
            shutil.copyfileobj(file.file, fh, length=8 * 1024 * 1024)
        size_bytes = os.path.getsize(local)
        duration = _ffprobe_duration(local)

        if is_video and _make_poster(local, os.path.join(workdir, "poster.jpg"), duration):
            with open(os.path.join(workdir, "poster.jpg"), "rb") as ph:
                s3().upload_fileobj(
                    ph, s.minio_bucket_thumbs, f"{video_id}/poster.jpg",
                    ExtraArgs={"ContentType": "image/jpeg"},
                )

        with open(local, "rb") as fh:
            s3().upload_fileobj(
                fh, s.minio_bucket_videos, key,
                ExtraArgs={"ContentType": file.content_type or "application/octet-stream"},
            )
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    video = Video(
        id=video_id, user_id=user_id,
        original_filename=file.filename or f"upload{ext}",
        minio_key=key, status="stored",
        duration_s=round(duration, 3) or None,
        size_bytes=size_bytes,
    )
    session.add(video)
    await session.commit()
    await session.refresh(video)

    # Upload = storage only. The IV2/TransNet/SG-DETR/KG pipeline is triggered by
    # add-to-index (POST /indexes/{id}/videos), not here. (1 video = 1 index.)
    return success_response(VideoOut.model_validate(video, from_attributes=True).model_dump(mode="json"))


# Direct-to-S3 upload (browser PUTs straight to S3 — no pod relay).
# Cuts the upload latency: the old POST /videos relayed every byte through the
# pod and then re-uploaded pod→S3 (a 2s+ leg for a 24MB file, invisible to the
# progress bar). Here the browser uploads directly and extracts duration+poster
# client-side, so the pod never touches the file.


class UploadUrlRequest(BaseModel):
    filename: str = Field(min_length=1)
    content_type: str = "application/octet-stream"


class RegisterRequest(BaseModel):
    video_id: UUID
    key: str = Field(min_length=1)
    original_filename: str = Field(min_length=1)
    duration_s: float | None = None


def _owned_key_ext(user_id: UUID, video_id: UUID, key: str) -> str | None:
    """Return the file extension iff `key` is the canonical key we mint for this
    user+video (`{user}/{video}{ext}`) with an allowed extension; else None.
    Guards register against pointing at an arbitrary / another user's object."""
    if not key.startswith(f"{user_id}/{video_id}"):
        return None
    return next((e for e in _VIDEO_EXTS + _AUDIO_EXTS if key.lower().endswith(e)), None)


@router.post("/upload-url")
async def create_upload_url(body: UploadUrlRequest, payload: TokenPayload = Depends(require_user)):
    """Mint presigned PUT URLs so the browser uploads the video (and a
    client-generated poster) straight to S3. Returns the canonical key + ids."""
    s = get_settings()
    ext = next((e for e in _VIDEO_EXTS + _AUDIO_EXTS if body.filename.lower().endswith(e)), None)
    if ext is None:
        raise HTTPException(
            400,
            f"Unsupported file extension (allowed video: {','.join(_VIDEO_EXTS)}; "
            f"audio: {','.join(_AUDIO_EXTS)})",
        )
    from main.storage.minio import presigned_put
    user_id = UUID(payload.sub)
    video_id = uuid4()
    key = f"{user_id}/{video_id}{ext}"
    return success_response({
        "video_id": str(video_id),
        "key": key,
        "video_put_url": presigned_put(s.minio_bucket_videos, key, body.content_type or "application/octet-stream"),
        "poster_put_url": presigned_put(s.minio_bucket_thumbs, f"{video_id}/poster.jpg", "image/jpeg"),
    })


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_upload(
    body: RegisterRequest,
    payload: TokenPayload = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    """Create the Assets row after the browser finished its direct-to-S3 PUT.
    HEADs the object first so a failed/forged upload can't create an orphan row."""
    s = get_settings()
    user_id = UUID(payload.sub)
    ext = _owned_key_ext(user_id, body.video_id, body.key)
    if ext is None:
        raise HTTPException(403, "Key does not belong to the authenticated user / video, or has an unsupported type")
    try:
        head = s3().head_object(Bucket=s.minio_bucket_videos, Key=body.key)
        size_bytes = int(head["ContentLength"])
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(409, "Uploaded object not found in storage — PUT may have failed") from exc

    video = Video(
        id=body.video_id, user_id=user_id,
        original_filename=body.original_filename,
        minio_key=body.key, status="stored",
        duration_s=round(body.duration_s, 3) if body.duration_s else None,
        size_bytes=size_bytes,
    )
    session.add(video)
    await session.commit()
    await session.refresh(video)
    return success_response(VideoOut.model_validate(video, from_attributes=True).model_dump(mode="json"))


def _ffprobe_duration(path: str) -> float:
    """Container duration in seconds (0.0 if ffprobe fails)."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nokey=1:noprint_wrappers=1", path],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        return float(out)
    except Exception:  # noqa: BLE001
        return 0.0


def _make_poster(src: str, dst: str, duration: float) -> bool:
    """Grab one representative frame as a poster thumbnail (480px wide JPEG).

    Seeks ~1s in (or mid-clip for very short videos) to avoid a black first
    frame. Best-effort: returns False if ffmpeg is missing or fails.
    """
    at = 1.0 if duration > 2 else max(0.0, duration / 2.0)
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-ss", f"{at:.2f}", "-i", src, "-frames:v", "1",
             "-vf", "scale=480:-2", "-loglevel", "error", dst],
            check=True,
        )
        return os.path.isfile(dst) and os.path.getsize(dst) > 0
    except Exception:  # noqa: BLE001
        return False


@router.post("/chunked", status_code=status.HTTP_202_ACCEPTED)
async def upload_chunked(
    file: UploadFile = File(...),
    chunk_seconds: int = Form(300),
    index_title: str | None = Form(None),
    index_id: str | None = Form(None),
    payload: TokenPayload = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    """Ingest a LONG video by splitting it into ~`chunk_seconds` windows so each
    chunk fits GPU memory + the per-job ingest timeout (Option B for long videos).

    The chunks are grouped under one Index (cross-chunk KG + search) and each
    carries `parent_video_id` + `offset_s` so retrieval can reconstruct global
    timestamps (global_t = offset_s + local_t). ffmpeg stream-copies on keyframe
    boundaries (no re-encode), so chunk durations vary slightly around
    `chunk_seconds`; `offset_s` is the exact cumulative start of each chunk.

    NOTE: for multi-GB sources POST this through the SSH local-forward
    (127.0.0.1:11101) — the Cloudflare edge caps large request bodies.
    """
    s = get_settings()
    user_id = UUID(payload.sub)
    filename = file.filename or "upload.mp4"
    ext = next((e for e in _VIDEO_EXTS if filename.lower().endswith(e)), None)
    if ext is None:
        raise HTTPException(400, f"chunked ingest supports video only ({','.join(_VIDEO_EXTS)})")
    if chunk_seconds < 30:
        raise HTTPException(400, "chunk_seconds must be >= 30")

    workdir = tempfile.mkdtemp(prefix="chunked_")
    src = os.path.join(workdir, f"src{ext}")
    try:
        with open(src, "wb") as fh:
            shutil.copyfileobj(file.file, fh, length=8 * 1024 * 1024)

        # Stream-copy split on keyframe boundaries; reset each chunk's PTS to 0
        # so every chunk ingests as a normal 0-based video.
        seg_tmpl = os.path.join(workdir, f"chunk_%04d{ext}")
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", src, "-c", "copy", "-map", "0",
                 "-f", "segment", "-segment_time", str(chunk_seconds),
                 "-reset_timestamps", "1", "-loglevel", "error", seg_tmpl],
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            raise HTTPException(500, f"ffmpeg split failed: {exc}") from exc

        chunk_files = sorted(f for f in os.listdir(workdir) if f.startswith("chunk_"))
        if not chunk_files:
            raise HTTPException(500, "ffmpeg produced no chunks")

        base = filename.rsplit("/", 1)[-1]
        parent_video_id = uuid4()
        # Join an existing index (e.g. add several long videos to one collection)
        # or create a fresh one for this source.
        start_pos = 0
        if index_id:
            idx = await session.get(Index, UUID(index_id))
            if not idx or idx.user_id != user_id:
                raise HTTPException(404, "Index not found")
            mx = (await session.execute(
                select(func.max(IndexVideo.position)).where(IndexVideo.index_id == idx.id)
            )).scalar()
            start_pos = (mx + 1) if mx is not None else 0
        else:
            idx = Index(
                user_id=user_id,
                title=(index_title or base),
                description=f"Chunked ingest of {base} ({len(chunk_files)} parts)",
            )
            session.add(idx)
            await session.flush()  # populate idx.id

        chunks_out: list[dict] = []
        chunk_ids: list = []
        offset = 0.0
        n = len(chunk_files)
        for i, cf in enumerate(chunk_files):
            cpath = os.path.join(workdir, cf)
            dur = _ffprobe_duration(cpath)
            cvid = uuid4()
            key = f"{user_id}/{cvid}{ext}"
            with open(cpath, "rb") as fh:
                s3().upload_fileobj(
                    fh, s.minio_bucket_videos, key,
                    ExtraArgs={"ContentType": file.content_type or "video/mp4"},
                )
            session.add(Video(
                id=cvid, user_id=user_id,
                original_filename=f"{base} [part {i + 1}/{n}]",
                minio_key=key, status="queued",
                parent_video_id=parent_video_id, offset_s=round(offset, 3),
            ))
            chunk_ids.append(cvid)
            chunks_out.append({
                "video_id": str(cvid), "part": i + 1,
                "offset_s": round(offset, 3), "duration_s": round(dur, 3),
            })
            offset += dur
        # Insert all chunk Video rows first so the index_videos FK (video_id ->
        # videos.id) is satisfied — SQLAlchemy batches cross-table inserts and
        # won't reliably order them otherwise.
        await session.flush()
        for i, cvid in enumerate(chunk_ids):
            session.add(IndexVideo(index_id=idx.id, video_id=cvid, position=start_pos + i))
        await session.commit()

        for c in chunks_out:
            get_queue(VIDEO_INDEX_QUEUE).enqueue(
                "main.workers.queue_worker.index_video", c["video_id"], job_timeout=3600,
            )

        return success_response({
            "parent_video_id": str(parent_video_id),
            "index_id": str(idx.id),
            "chunk_seconds": chunk_seconds,
            "chunk_count": n,
            "total_duration_s": round(offset, 3),
            "chunks": chunks_out,
        })
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


@router.get("")
async def list_videos(payload: TokenPayload = Depends(require_user), session: AsyncSession = Depends(get_session)):
    user_id = UUID(payload.sub)
    rows = (await session.execute(select(Video).where(Video.user_id == user_id).order_by(Video.created_at.desc()))).scalars().all()

    # Chunked long videos are stored as N child parts (parent_video_id set). The
    # parts stay in the DB / index for processing + retrieval, but the library UI
    # should show ONE entry per long video — collapse the parts into a single
    # synthetic parent entry (id = parent_video_id) and hide the parts themselves.
    standalone = [v for v in rows if v.parent_video_id is None]
    groups: dict = {}
    for v in rows:
        if v.parent_video_id is not None:
            groups.setdefault(v.parent_video_id, []).append(v)

    out = [VideoOut.model_validate(v, from_attributes=True).model_dump(mode="json") for v in standalone]
    for parent_id, kids in groups.items():
        kids.sort(key=lambda k: (k.offset_s or 0.0))
        first = kids[0]
        statuses = {k.status for k in kids}
        if statuses == {"ready"}:
            agg = "ready"
        elif statuses & {"processing", "queued"}:
            agg = "processing"
        elif "error" in statuses:
            agg = "error"
        else:
            agg = "ready"
        base = (first.original_filename or "").split(" [part ")[0] or first.original_filename
        out.append({
            "id": str(parent_id),
            "user_id": str(user_id),
            "original_filename": base,
            "duration_s": sum((k.duration_s or 0.0) for k in kids) or None,
            "size_bytes": (sum((k.size_bytes or 0) for k in kids) or None),
            "status": agg,
            "shot_count": (sum((k.shot_count or 0) for k in kids) or None),
            "error": None,
            "created_at": min(k.created_at for k in kids).isoformat(),
            "modality": first.modality,
            "has_video": first.has_video,
            "has_audio": first.has_audio,
            "global_summary": None,
            "parent_video_id": None,
            "offset_s": None,
        })

    out.sort(key=lambda d: d["created_at"], reverse=True)
    return success_response(out)


@router.get("/{video_id}")
async def get_video(video_id: UUID, payload: TokenPayload = Depends(require_user), session: AsyncSession = Depends(get_session)):
    v = await session.get(Video, video_id)
    if not v or v.user_id != UUID(payload.sub):
        raise HTTPException(404, "Video not found")
    return success_response(VideoOut.model_validate(v, from_attributes=True).model_dump(mode="json"))


@router.delete("/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_video(
    video_id: UUID,
    payload: TokenPayload = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    """Delete a video and its derived artifacts.

    Removes the row from Postgres, the MP4 from MinIO, any shot thumbnails and feature
    cache, plus every Qdrant point referencing this video_id. Cleanly handles videos
    in any status (queued/indexing/ready/error) — only the artifacts that exist are
    deleted; the rest is best-effort.
    """
    v = await session.get(Video, video_id)
    if not v or v.user_id != UUID(payload.sub):
        raise HTTPException(404, "Video not found")

    s = get_settings()

    # MinIO: source mp4, shot thumbs (best-effort).
    try:
        s3().delete_object(Bucket=s.minio_bucket_videos, Key=v.minio_key)
    except Exception:
        pass
    try:
        s3().delete_object(Bucket=s.minio_bucket_videos, Key=f"features/{video_id}.npz")
    except Exception:
        pass
    # Lighthouse feature caches (visual + audio).
    try:
        objs = s3().list_objects_v2(
            Bucket=s.minio_bucket_videos,
            Prefix=f"features/{video_id}/",
        )
        for obj in objs.get("Contents", []) or []:
            s3().delete_object(Bucket=s.minio_bucket_videos, Key=obj["Key"])
    except Exception:
        pass
    try:
        objs = s3().list_objects_v2(Bucket=s.minio_bucket_thumbs, Prefix=f"{video_id}/")
        for obj in objs.get("Contents", []) or []:
            s3().delete_object(Bucket=s.minio_bucket_thumbs, Key=obj["Key"])
    except Exception:
        pass

    # Qdrant: drop every shot/segment tied to this video_id across the three
    # collections the ingest pipeline writes to.
    try:
        from qdrant_client.http import models as qm

        from main.qdrant_util import get_qdrant_client
        client = get_qdrant_client()
        selector = qm.FilterSelector(
            filter=qm.Filter(must=[
                qm.FieldCondition(key="video_id", match=qm.MatchValue(value=str(video_id))),
            ]),
        )
        for coll in (s.qdrant_collection, "jockey_segments_text", "jockey_videos"):
            try:
                client.delete(collection_name=coll, points_selector=selector)
            except Exception:
                pass
    except Exception:
        pass

    # Postgres: clear FK-referencing rows first, then the video row.
    from sqlalchemy import delete as sa_delete
    await session.execute(sa_delete(IndexingJob).where(IndexingJob.video_id == video_id))
    await session.delete(v)
    await session.commit()
    return None


@router.get("/{video_id}/stream")
async def stream_url(video_id: UUID, payload: TokenPayload = Depends(require_user), session: AsyncSession = Depends(get_session)):
    v = await session.get(Video, video_id)
    if not v or v.user_id != UUID(payload.sub):
        raise HTTPException(404, "Video not found")
    s = get_settings()
    return success_response({"url": presigned_get(s.minio_bucket_videos, v.minio_key)})


@router.get("/{video_id}/thumb/{shot_idx}")
async def thumb_url(
    video_id: UUID,
    shot_idx: int,
    payload: TokenPayload = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    """Return a presigned URL for a shot thumbnail (symmetric with /stream).

    The indexing worker writes JPEGs to ``thumbs/{video_id}/{idx}.jpg``. We return
    JSON ``{url}`` instead of a 307 redirect because ``<img src>`` does not send the
    Bearer token, so a redirect-guarded endpoint would fail before the redirect could
    fire. The frontend fetches the URL with axios (which carries the token) and then
    points ``<img src>`` at the presigned MinIO URL directly.
    """
    v = await session.get(Video, video_id)
    if not v or v.user_id != UUID(payload.sub):
        raise HTTPException(404, "Video not found")
    s = get_settings()
    url = presigned_get(s.minio_bucket_thumbs, f"{video_id}/{shot_idx}.jpg")
    return success_response({"url": url})


@router.get("/{video_id}/poster")
async def poster_url(
    video_id: UUID,
    payload: TokenPayload = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    """Presigned URL for the asset's poster thumbnail (generated at upload).

    Falls back to shot 0's thumbnail for videos ingested before posters existed,
    so the Assets list shows something for every video regardless of status.
    404s until a frame exists (the UI shows the play-icon placeholder until then).
    """
    v = await session.get(Video, video_id)
    if not v or v.user_id != UUID(payload.sub):
        raise HTTPException(404, "Video not found")
    s = get_settings()
    for k in (f"{video_id}/poster.jpg", f"{video_id}/0.jpg"):
        try:
            s3().head_object(Bucket=s.minio_bucket_thumbs, Key=k)
        except Exception:
            continue
        return success_response({"url": presigned_get(s.minio_bucket_thumbs, k)})
    raise HTTPException(404, "No thumbnail yet")
