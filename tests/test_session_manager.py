"""Tests for Redis-backed tournament sessions and database lookups."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator

import fakeredis.aioredis
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.db.base import Base
from src.db.models import BlindStructure, PositionLabel
from src.services.session_manager import SessionManager, TableSession


@pytest.fixture
def db_session() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as session:
        yield session
    engine.dispose()


def test_get_or_create_session_initializes_defaults() -> None:
    async def scenario() -> None:
        redis_client = fakeredis.aioredis.FakeRedis()
        manager = SessionManager(redis_client, ttl=60)

        session = await manager.get_or_create_session(42)

        assert session == TableSession(user_id=42)
        assert await redis_client.ttl(manager._make_key(42)) > 0
        assert await manager.get_or_create_session(42) == session
        await redis_client.aclose()

    asyncio.run(scenario())


def test_next_hand_moves_button_and_wraps() -> None:
    async def scenario() -> None:
        redis_client = fakeredis.aioredis.FakeRedis()
        manager = SessionManager(redis_client)
        await manager.save_session(TableSession(user_id=7, table_size=6, btn_position=6))

        wrapped = await manager.next_hand(7)
        moved = await manager.next_hand(7)

        assert wrapped.btn_position == 1
        assert moved.btn_position == 2
        await redis_client.aclose()

    asyncio.run(scenario())


def test_change_table_size_safely_adjusts_seats() -> None:
    async def scenario() -> None:
        redis_client = fakeredis.aioredis.FakeRedis()
        manager = SessionManager(redis_client)
        await manager.save_session(
            TableSession(user_id=8, table_size=9, hero_seat=9, btn_position=8)
        )

        session = await manager.change_table_size(8, 6)

        assert session.table_size == 6
        assert session.hero_seat == 6
        assert session.btn_position == 6
        assert await manager.get_or_create_session(8) == session
        await redis_client.aclose()

    asyncio.run(scenario())


def test_position_label_and_stack_bb_use_sqlite(db_session: Session) -> None:
    db_session.add_all(
        [
            PositionLabel(table_size=6, seat_index=5, label="CO"),
            BlindStructure(
                structure_id="TURBO",
                level=3,
                sb_chips=250,
                bb_chips=500,
                ante_chips=50,
            ),
        ]
    )
    db_session.commit()
    manager = SessionManager(fakeredis.aioredis.FakeRedis())
    table_session = TableSession(
        user_id=9,
        table_size=6,
        btn_position=2,
        hero_seat=1,
        stack_chips=12_750,
        blind_level=3,
    )

    assert manager.get_hero_position_label(table_session, db_session) == "CO"
    assert manager.get_stack_bb(table_session, db_session) == 25.5

    unknown = table_session.model_copy(update={"structure_id": "MISSING"})
    assert manager.get_stack_bb(unknown, db_session) == 127.5
