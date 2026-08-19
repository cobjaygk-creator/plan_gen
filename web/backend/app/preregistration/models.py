"""Persistent campaign-level data model for game preregistrations."""
import enum
from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PreRegistrationType(str, enum.Enum):
    NEW_GAME = "NEW_GAME"
    GAME_UPDATE = "GAME_UPDATE"
    NEW_CLASS = "NEW_CLASS"
    NEW_CHARACTER = "NEW_CHARACTER"
    MAJOR_UPDATE = "MAJOR_UPDATE"
    SEASON_UPDATE = "SEASON_UPDATE"
    ANNIVERSARY = "ANNIVERSARY"
    NEW_SERVER = "NEW_SERVER"
    RETURN_CAMPAIGN = "RETURN_CAMPAIGN"
    SPECIAL_EVENT = "SPECIAL_EVENT"
    OTHER = "OTHER"


class GamePreRegistration(Base):
    """One row per landing-page campaign, not one row per game."""

    __tablename__ = "game_preregistrations"
    __table_args__ = (
        UniqueConstraint(
            "normalized_game_name", "campaign_name", "preregistration_type", "preregistration_start_date",
            name="uq_game_preregistration_campaign",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_name: Mapped[str] = mapped_column(String(255), index=True)
    normalized_game_name: Mapped[str] = mapped_column(String(255), index=True)
    campaign_name: Mapped[str] = mapped_column(String(500))
    preregistration_type: Mapped[str] = mapped_column(String(32), index=True)
    developer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    publisher: Mapped[str | None] = mapped_column(String(255), nullable=True)
    genre: Mapped[str | None] = mapped_column(String(100), nullable=True)
    platform: Mapped[str | None] = mapped_column(Text, nullable=True)
    preregistration_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    preregistration_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    release_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    update_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    official_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    preregistration_url: Mapped[str] = mapped_column(String(1000), unique=True)
    thumbnail_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    main_visual_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="ongoing", index=True)
    is_game_preregistration: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_release_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
