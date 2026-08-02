"""SQLAlchemy 2.0 ORM models for preflop and postflop strategy data."""

from typing import Optional

from sqlalchemy import Index, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class PositionLabel(Base):
    __tablename__ = "position_labels"

    table_size: Mapped[int] = mapped_column(primary_key=True)
    seat_index: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(16), nullable=False)


class NashPushFold(Base):
    __tablename__ = "nash_pushfold"
    __table_args__ = (Index("ix_nash_pushfold_lookup", "table_size", "position", "stack_bb"),)

    table_size: Mapped[int] = mapped_column(primary_key=True)
    position: Mapped[str] = mapped_column(String(16), primary_key=True)
    stack_bb: Mapped[int] = mapped_column(primary_key=True)
    has_ante: Mapped[bool] = mapped_column(primary_key=True)
    action: Mapped[str] = mapped_column(String(16), primary_key=True)
    range_str: Mapped[str] = mapped_column(nullable=False)


class IcmPushFold(Base):
    __tablename__ = "icm_pushfold"
    __table_args__ = (Index("ix_icm_pushfold_lookup", "table_size", "position", "payout_stage", "stack_bb"),)

    table_size: Mapped[int] = mapped_column(primary_key=True)
    position: Mapped[str] = mapped_column(String(16), primary_key=True)
    stack_bb: Mapped[int] = mapped_column(primary_key=True)
    payout_stage: Mapped[str] = mapped_column(String(16), primary_key=True)
    has_ante: Mapped[bool] = mapped_column(primary_key=True)
    action: Mapped[str] = mapped_column(String(16), primary_key=True)
    range_str: Mapped[str] = mapped_column(nullable=False)


class FacingActionRange(Base):
    __tablename__ = "facing_action_ranges"
    __table_args__ = (Index("ix_facing_action_ranges_lookup", "hero_position", "villain_position", "stack_bb"),)

    hero_position: Mapped[str] = mapped_column(String(16), primary_key=True)
    villain_position: Mapped[str] = mapped_column(String(16), primary_key=True)
    villain_action: Mapped[str] = mapped_column(String(16), primary_key=True)
    stack_bb: Mapped[int] = mapped_column(primary_key=True)
    opponent_style: Mapped[str] = mapped_column(String(16), primary_key=True)
    range_3bet_push: Mapped[Optional[str]] = mapped_column(nullable=True)
    range_3bet_raise: Mapped[Optional[str]] = mapped_column(nullable=True)
    range_call: Mapped[Optional[str]] = mapped_column(nullable=True)


class OpenRange(Base):
    __tablename__ = "open_ranges"
    __table_args__ = (Index("ix_open_ranges_lookup", "position", "stack_bb", "style"),)

    position: Mapped[str] = mapped_column(String(16), primary_key=True)
    stack_bb: Mapped[int] = mapped_column(primary_key=True)
    style: Mapped[str] = mapped_column(String(16), primary_key=True)
    range_str: Mapped[str] = mapped_column(nullable=False)


class BlindStructure(Base):
    __tablename__ = "blind_structures"
    __table_args__ = (Index("ix_blind_structures_structure_level", "structure_id", "level"),)

    structure_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    level: Mapped[int] = mapped_column(primary_key=True)
    sb_chips: Mapped[int] = mapped_column(nullable=False)
    bb_chips: Mapped[int] = mapped_column(nullable=False)
    ante_chips: Mapped[int] = mapped_column(nullable=False)


class FlopTexture(Base):
    __tablename__ = "flop_textures"

    texture_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    description: Mapped[str] = mapped_column(nullable=False)


class HandBucket(Base):
    __tablename__ = "hand_buckets"

    bucket_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    description: Mapped[str] = mapped_column(nullable=False)


class PostflopStrategy(Base):
    __tablename__ = "postflop_strategies"
    __table_args__ = (
        Index(
            "ix_postflop_strategies_lookup",
            "pot_type",
            "hero_role",
            "hero_position",
            "texture_id",
            "bucket_id",
        ),
    )

    pot_type: Mapped[str] = mapped_column(String(8), primary_key=True)
    hero_role: Mapped[str] = mapped_column(String(8), primary_key=True)
    hero_position: Mapped[str] = mapped_column(String(8), primary_key=True)
    texture_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    bucket_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    stack_depth: Mapped[str] = mapped_column(String(16), primary_key=True)
    action_check_pct: Mapped[int] = mapped_column(nullable=False)
    action_bet_pct: Mapped[int] = mapped_column(nullable=False)
    action_raise_pct: Mapped[int] = mapped_column(nullable=False)
    recommended_sizing: Mapped[str] = mapped_column(String(32), nullable=False)