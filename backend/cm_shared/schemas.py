"""Pydantic schemas shared between services."""
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


# -------- Users / Auth --------
class UserOut(BaseModel):
    id: UUID
    email: EmailStr
    role: Literal["admin", "user"]
    is_active: bool = True
    created_at: datetime


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class GoogleAuthRequest(BaseModel):
    """The ID-token (JWT `credential`) returned by Google Identity Services."""
    credential: str


# -------- Videos --------
VideoStatus = Literal["stored", "queued", "processing", "ready", "error", "flagged", "rejected"]
VideoModality = Literal["video_audio", "video_only", "audio_only"]


class VideoOut(BaseModel):
    id: UUID
    user_id: UUID
    original_filename: str
    duration_s: float | None = None
    size_bytes: int | None = None
    status: VideoStatus
    shot_count: int | None = None
    error: str | None = None
    created_at: datetime
    modality: VideoModality | None = None
    has_video: bool | None = None
    has_audio: bool | None = None
    global_summary: str | None = None
    # Set on chunks produced by POST /api/v1/videos/chunked (Option B). `offset_s`
    # is the chunk's start time within the full source; add it to a segment's
    # local t_start/t_end to get the timestamp in the original long video.
    parent_video_id: UUID | None = None
    offset_s: float | None = None


# -------- Grounding --------
class GroundQuery(BaseModel):
    query: str = Field(min_length=1, max_length=512)


class ShotResult(BaseModel):
    idx: int
    t_start: float
    t_end: float
    relevance: float
    asr_text: str | None = None


class Span(BaseModel):
    t_start: float
    t_end: float
    score: float


class GroundingResult(BaseModel):
    video_id: UUID
    query: str
    shots: list[ShotResult]
    spans: list[Span]


# -------- Chat / Conversations --------
class ChatMessageIn(BaseModel):
    conversation_id: UUID | None = None
    video_id: UUID | None = None
    video_ids: list[UUID] | None = None
    # When set, the chat is scoped to an Index (lecture series / collection).
    # `video_ids` may be empty (whole index) or a subset of its videos.
    index_id: UUID | None = None
    # Optional base64 data-URL image attached to the turn. Used by the
    # `find_scene_by_image` tool to locate the scene in a video matching it.
    image: str | None = None
    message: str = Field(min_length=1)


class MessageOut(BaseModel):
    id: UUID
    conversation_id: UUID
    role: Literal["user", "assistant"]
    content: str
    thoughts: list[dict[str, Any]] | None = None
    tool_calls: list[dict[str, Any]] | None = None
    created_at: datetime


# -------- Token usage --------
class TokenUsageLog(BaseModel):
    user_id: UUID
    conversation_id: UUID | None = None
    model: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float = 0.0
