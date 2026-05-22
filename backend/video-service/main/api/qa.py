from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from cm_shared.auth import TokenPayload, require_user
from cm_shared.db import get_session
from cm_shared.response import success_response
from main.models.video import Video
from main.storage.minio import presigned_get
from main.settings import get_settings

router = APIRouter(prefix="/api/v1/videos", tags=["qa"])


class QaRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2048)
    t_start: float | None = None
    t_end: float | None = None


@router.post("/{video_id}/qa")
async def qa(
    video_id: UUID,
    body: QaRequest,
    payload: TokenPayload = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    v = await session.get(Video, video_id)
    if not v or v.user_id != UUID(payload.sub):
        raise HTTPException(404, "Video not found")

    s = get_settings()
    # Qwen3-VL runs inside the docker network — use the internal endpoint, not the
    # browser-facing one, otherwise it can't fetch the video.
    video_url = presigned_get(s.minio_bucket_videos, v.minio_key, expires=3600, public=False)

    # When the user asks about a specific time range, pull the Whisper transcript
    # for that window out of Qdrant and prepend it to the prompt. Qwen3-VL only sees
    # frames otherwise — for tutorial-style videos that's barely useful, since the
    # information is in the spoken audio.
    transcript = ""
    if body.t_start is not None and body.t_end is not None:
        transcript = _fetch_transcript_window(video_id, body.t_start, body.t_end, s)

    # Phrasing directive: Qwen3-VL receives a frame batch and defaults to phrases like
    # "Based on the provided images". The user is interacting with a video, not a slide
    # deck — force the answer to talk about "the video" / "this clip".
    phrasing_rule = (
        "Phrasing: refer to what you're analyzing as 'the video' or 'this clip', "
        "never 'the images', 'the frames', 'the pictures', or 'the provided images'. "
        "Do not mention that you are seeing a sequence of frames; talk about the action and content."
    )

    prompt = body.question
    if transcript:
        prompt = (
            f"Transcript of the spoken audio in this segment:\n{transcript}\n\n"
            f"Question: {body.question}\n\n"
            "Use both the video's frames AND the transcript above to answer. "
            "If the answer is in the transcript, quote or paraphrase it directly.\n\n"
            f"{phrasing_rule}"
        )
    else:
        prompt = f"{body.question}\n\n{phrasing_rule}"

    try:
        import json as _json
        from jockey.open_source.video_qa import VideoQA  # type: ignore
        client = VideoQA(api_key=s.openrouter_api_key)
        if body.t_start is not None and body.t_end is not None:
            raw = await client.analyze_range(
                video_path=video_url,
                start_sec=body.t_start,
                end_sec=body.t_end,
                prompt=prompt,
            )
        else:
            raw = await client.freeform(video_path=video_url, prompt=prompt)
        # VideoQA returns a JSON-encoded string; surface the text field if present.
        try:
            parsed = _json.loads(raw)
            answer = parsed.get("text", raw) if isinstance(parsed, dict) else raw
        except (_json.JSONDecodeError, TypeError):
            answer = raw
    except Exception as exc:
        raise HTTPException(502, f"QA backend error: {exc}") from exc

    return success_response({"video_id": str(video_id), "question": body.question, "answer": answer})


def _fetch_transcript_window(video_id: UUID, t_start: float, t_end: float, s) -> str:
    """Pull stored Whisper transcripts for every shot overlapping [t_start, t_end].

    Reads from Qdrant rather than re-running Whisper — the indexer already
    transcribed each shot and stored ``asr_text`` in the payload.
    """
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.http import models as qm
        client = QdrantClient(host=s.qdrant_host, port=s.qdrant_port)
        points, _ = client.scroll(
            collection_name=s.qdrant_collection,
            scroll_filter=qm.Filter(must=[
                qm.FieldCondition(key="video_id", match=qm.MatchValue(value=str(video_id))),
            ]),
            with_payload=True,
            with_vectors=False,
            limit=1000,
        )
    except Exception:
        return ""

    # Keep shots whose [t_start, t_end] overlaps the requested window.
    overlapping = [
        p.payload for p in points
        if p.payload.get("t_end", 0) > t_start and p.payload.get("t_start", 0) < t_end
    ]
    overlapping.sort(key=lambda p: p.get("shot_idx", 0))
    return "\n".join((p.get("asr_text") or "").strip() for p in overlapping if (p.get("asr_text") or "").strip())
