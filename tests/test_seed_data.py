"""Coverage and idempotency checks for generated tournament data."""

from __future__ import annotations

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from src.db.base import Base
from src.db.models import FacingActionRange, IcmPushFold, LimpCallRange, LimpRange, NashPushFold, OpenRange, PostflopStrategy
from src.db.seed_data import POSITIONS_BY_SIZE, generate_tournament_data, seed_tournament_data


def test_generated_data_has_complete_strategy_dimensions() -> None:
    data = generate_tournament_data()

    assert set(POSITIONS_BY_SIZE) == set(range(2, 10))
    assert all(len(positions) == size for size, positions in POSITIONS_BY_SIZE.items())
    pushfold_positions = sum(len(positions) - 1 for positions in POSITIONS_BY_SIZE.values())
    assert len(data[IcmPushFold]) == pushfold_positions * 6 * 2 * 3
    assert len(data[NashPushFold]) == pushfold_positions * 6 * 2
    assert len(data[OpenRange]) == 189
    assert len(data[LimpRange]) == 189
    assert len(data[LimpCallRange]) == 210
    assert len(data[FacingActionRange]) == 1944
    assert len(data[PostflopStrategy]) == 2 * 3 * 2 * 5 * 7 * 3
    assert all(
        row["action_check_pct"] + row["action_bet_pct"] + row["action_raise_pct"] == 100
        for row in data[PostflopStrategy]
    )


def test_seed_is_idempotent_and_updates_existing_rows() -> None:
    database_engine = create_engine("sqlite:///:memory:")
    factory = sessionmaker(bind=database_engine)

    first_counts = seed_tournament_data(factory, database_engine)
    with factory.begin() as session:
        row = session.get(OpenRange, {"position": "CO", "stack_bb": 30, "style": "REG"})
        assert row is not None
        row.range_str = "AA"

    second_counts = seed_tournament_data(factory, database_engine)
    with factory() as session:
        total = session.scalar(select(func.count()).select_from(OpenRange))
        restored = session.get(OpenRange, {"position": "CO", "stack_bb": 30, "style": "REG"})

    assert first_counts == second_counts
    assert total == first_counts["open_ranges"]
    assert restored is not None and restored.range_str != "AA"

    Base.metadata.drop_all(database_engine)
