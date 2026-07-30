"""Redis-backed tournament table session management."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models import BlindStructure, PositionLabel


class TableSession(BaseModel):
    """Mutable state for a player's current tournament table."""

    user_id: int
    table_size: int = Field(default=9, ge=2, le=9)
    btn_position: int = Field(default=1, ge=1)
    hero_seat: int = Field(default=1, ge=1)
    stack_chips: int = Field(default=25_000, ge=1)
    blind_level: int = Field(default=1, ge=1)
    icm_stage: Literal["NORMAL", "BUBBLE", "FINAL_TABLE"] = "NORMAL"
    opponent_style: Literal["REG", "TIGHT", "LOOSE"] = "REG"
    has_ante: bool = True
    structure_id: str = "TURBO"

    @model_validator(mode="after")
    def validate_seats(self) -> "TableSession":
        if self.btn_position > self.table_size:
            raise ValueError("btn_position must not exceed table_size")
        if self.hero_seat > self.table_size:
            raise ValueError("hero_seat must not exceed table_size")
        return self


class SessionManager:
    """Persist and update player sessions in Redis."""

    def __init__(self, redis_client: Redis, ttl: int = 86_400) -> None:
        if ttl <= 0:
            raise ValueError("ttl must be positive")
        self._redis = redis_client
        self._ttl = ttl

    @staticmethod
    def _make_key(user_id: int) -> str:
        return f"poker_session:{user_id}"

    async def get_or_create_session(self, user_id: int) -> TableSession:
        data = await self._redis.get(self._make_key(user_id))
        if data is not None:
            return TableSession.model_validate_json(data)

        session = TableSession(user_id=user_id)
        await self.save_session(session)
        return session

    async def save_session(self, session: TableSession) -> None:
        await self._redis.set(
            self._make_key(session.user_id),
            session.model_dump_json(),
            ex=self._ttl,
        )

    async def next_hand(self, user_id: int) -> TableSession:
        session = await self.get_or_create_session(user_id)
        session.btn_position = (session.btn_position % session.table_size) + 1
        await self.save_session(session)
        return session

    async def change_table_size(self, user_id: int, new_size: int) -> TableSession:
        session = await self.get_or_create_session(user_id)
        bounded_size = max(2, min(9, new_size))
        session.table_size = bounded_size
        session.hero_seat = min(session.hero_seat, bounded_size)
        session.btn_position = min(session.btn_position, bounded_size)
        await self.save_session(session)
        return session

    async def adjust_stack_chips(self, user_id: int, new_chips: int) -> TableSession:
        session = await self.get_or_create_session(user_id)
        session.stack_chips = max(1, new_chips)
        await self.save_session(session)
        return session

    def get_hero_position_label(self, session: TableSession, db_session: Session) -> str:
        seat_index = (session.hero_seat - session.btn_position) % session.table_size
        statement = select(PositionLabel).where(
            PositionLabel.table_size == session.table_size,
            PositionLabel.seat_index == seat_index,
        )
        row = db_session.scalar(statement)
        return row.label if row is not None else "UNKNOWN"

    def get_stack_bb(self, session: TableSession, db_session: Session) -> float:
        statement = select(BlindStructure).where(
            BlindStructure.structure_id == session.structure_id,
            BlindStructure.level == session.blind_level,
        )
        row = db_session.scalar(statement)
        bb_chips = row.bb_chips if row is not None else 100
        return round(session.stack_chips / bb_chips, 1)
