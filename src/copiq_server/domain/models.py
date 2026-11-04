"""SQLAlchemy models -- architecture.md section 12."""
from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


class Base(DeclarativeBase):
    pass


class ClipboardItem(Base):
    __tablename__ = "clipboard_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    content_type: Mapped[str] = mapped_column(String(64), nullable=False, default="text/plain")
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    client_id: Mapped[str] = mapped_column(String(128), nullable=False)
    has_possible_secret: Mapped[bool] = mapped_column(default=False, server_default="0")
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default=utc_now_iso)

    results: Mapped[list["AiActionResult"]] = relationship(
        back_populates="clipboard_item", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_clipboard_items_created_at", "created_at"),
        Index("ix_clipboard_items_dedup", "content_hash", "client_id", "created_at"),
    )


class AiActionResult(Base):
    __tablename__ = "ai_action_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clipboard_item_id: Mapped[int] = mapped_column(
        ForeignKey("clipboard_items.id", ondelete="CASCADE"), nullable=False
    )
    cache_key: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    parameters: Mapped[str | None] = mapped_column(Text, nullable=True)  # normalized JSON
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(16), nullable=False)
    provider_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default=utc_now_iso)

    clipboard_item: Mapped["ClipboardItem"] = relationship(back_populates="results")

    __table_args__ = (
        UniqueConstraint("cache_key", name="ux_ai_action_results_cache_key"),
        Index("ix_ai_action_results_item", "clipboard_item_id", "created_at"),
    )


class ApiKey(Base):
    """architecture.md section 27.1 -- one row per client, key stored hashed."""

    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default=utc_now_iso)
    revoked_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_used_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
