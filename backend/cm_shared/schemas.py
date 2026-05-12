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


# -------- Videos --------
VideoStatus = Literal["queued", "processing", "ready", "error"]


class VideoOut(BaseModel):
    id: UUID
    user_id: UUID
    original_filename: str
    duration_s: float | None = None
    status: VideoStatus
    shot_count: int | None = None
    error: str | None = None
    created_at: datetime


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
