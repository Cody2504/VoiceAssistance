from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import String, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from cm_shared.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    # Nullable: social-only users (e.g. Google sign-in) have no local password.
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Google subject id ("sub"), set when the account is linked to Google.
    google_sub: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True, index=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False, server_default="user")
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
