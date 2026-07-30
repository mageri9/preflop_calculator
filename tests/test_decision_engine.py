"""Integration-style tests for the decision service and its ORM lookups."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.db.base import Base
from src.db.models import FacingActionRange, NashPushFold, PostflopStrategy
from src.engine.decision_engine import DecisionEngine


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as database_session:
        yield database_session


@pytest.fixture
def engine(session: Session) -> DecisionEngine:
    return DecisionEngine()


def test_first_in_push_fold_uses_nearest_demo_range(session: Session, engine: DecisionEngine) -> None:
    session.add(NashPushFold(
        table_size=9, position="UTG", stack_bb=10, has_ante=True,
        action="PUSH_ONLY", range_str="22+, A2s+, K9s+, QTs+, ATo+, KJo+",
    ))
    session.commit()

    pushed = engine.get_preflop_first_in_decision(session, 9, "UTG", 11, "AJs")
    folded = engine.get_preflop_first_in_decision(session, 9, "UTG", 11, "72o")

    assert pushed.action == "PUSH"
    assert pushed.is_in_range is True
    assert pushed.range_stats is not None
    assert pushed.details["strategy_stack_bb"] == 10
    assert folded.action == "FOLD"
    assert folded.is_fallback is False


@pytest.mark.parametrize(
    ("combo", "expected_action"),
    [("AKs", "3BET_PUSH"), ("AJs", "3BET_RAISE"), ("ATs", "CALL"), ("72o", "FOLD")],
)
def test_facing_action_uses_priority_ranges(
    session: Session, engine: DecisionEngine, combo: str, expected_action: str
) -> None:
    session.add(FacingActionRange(
        hero_position="CO", villain_position="MP", villain_action="OPEN_2.5X",
        stack_bb=30, opponent_style="REG", range_3bet_push="TT+, AKs",
        range_3bet_raise="AJs+, KQs, JJ-99", range_call="ATs, KJs, QJs, 88-66",
    ))
    session.commit()

    result = engine.get_preflop_facing_action_decision(
        session, "CO", "MP", "OPEN_2.5X", 28, "REG", combo
    )

    assert result.action == expected_action
    assert result.is_fallback is False


def test_postflop_returns_strategy_frequencies_and_sizing(session: Session, engine: DecisionEngine) -> None:
    session.add(PostflopStrategy(
        pot_type="SRP", hero_role="PFR", hero_position="IP", texture_id="DRY_RAINBOW",
        bucket_id="TPTK", stack_depth="MEDIUM", action_check_pct=22,
        action_bet_pct=78, action_raise_pct=0, recommended_sizing="BET_33%_POT",
    ))
    session.commit()

    result = engine.get_postflop_decision(session, ["As", "Ks"], ["Kc", "7d", "2h"])

    assert result.action == "BET"
    assert result.frequencies == {"check_pct": 22, "bet_pct": 78, "raise_pct": 0}
    assert result.recommended_sizing == "BET_33%_POT"
    assert result.details["texture_id"] == "DRY_RAINBOW"
    assert result.details["bucket_id"] == "TPTK"


def test_empty_database_returns_safe_fallbacks(session: Session, engine: DecisionEngine) -> None:
    preflop = engine.get_preflop_first_in_decision(session, 9, "UTG", 10, "AJs")
    facing = engine.get_preflop_facing_action_decision(
        session, "CO", "MP", "OPEN_2.5X", 30, "REG", "AJs"
    )
    postflop = engine.get_postflop_decision(session, "AsKs", "Kc7d2h")

    assert (preflop.action, preflop.is_fallback) == ("FOLD", True)
    assert (facing.action, facing.is_fallback) == ("FOLD", True)
    assert (postflop.action, postflop.is_fallback) == ("CHECK", True)
    assert postflop.recommended_sizing == "CHECK"
