import os
import subprocess
import tempfile
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from cm_shared.auth import TokenPayload, require_user
from cm_shared.db import get_session
from cm_shared.response import success_response
from main.models.video import Video
from main.settings import get_settings
from main.storage.minio import download_to_path, presigned_get, s3

router = APIRouter(prefix="/api/v1/videos", tags=["edit"])


class Clip(BaseModel):
    t_start: float = Field(ge=0)
    t_end: float = Field(gt=0)


class EditRequest(BaseModel):
    clips: list[Clip] = Field(min_length=1, max_length=64)


@router.post("/{video_id}/edit")
async def edit(
    video_id: UUID,
    body: EditRequest,
    payload: TokenPayload = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    v = await session.get(Video, video_id)
    if not v or v.user_id != UUID(payload.sub):
        raise HTTPException(404, "Video not found")

    s = get_settings()
    edit_id = uuid4()
    tmpdir = tempfile.mkdtemp(prefix="jockey-edit-")
    try:
        src = os.path.join(tmpdir, "src.mp4")
        download_to_path(s.minio_bucket_videos, v.minio_key, src)

        segs = []
        for i, clip in enumerate(body.clips):
            seg = os.path.join(tmpdir, f"seg_{i}.mp4")
            subprocess.run(
                ["ffmpeg", "-y", "-i", src, "-ss", f"{clip.t_start:.2f}", "-to", f"{clip.t_end:.2f}",
                 "-c", "copy", "-loglevel", "error", seg],
                check=True,
            )
            segs.append(seg)

        list_path = os.path.join(tmpdir, "concat.txt")
        with open(list_path, "w") as f:
            for seg in segs:
                f.write(f"file '{seg}'\n")

        out_path = os.path.join(tmpdir, "out.mp4")
        subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_path,
             "-c", "copy", "-loglevel", "error", out_path],
            check=True,
        )

        key = f"{v.user_id}/{edit_id}.mp4"
        with open(out_path, "rb") as f:
            s3().upload_fileobj(f, s.minio_bucket_edits, key, ExtraArgs={"ContentType": "video/mp4"})

        url = presigned_get(s.minio_bucket_edits, key)
        return success_response({"edit_id": str(edit_id), "url": url, "clips": [c.model_dump() for c in body.clips]})
    except subprocess.CalledProcessError as exc:
        raise HTTPException(500, f"ffmpeg failed: {exc}") from exc
