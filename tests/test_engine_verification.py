"""Stage 4 verification tests for range math, matrix output, and latency."""

from __future__ import annotations

from statistics import median
from time import perf_counter

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.db.base import Base
from src.db.models import FacingActionRange, NashPushFold, PostflopStrategy
from src.engine.decision_engine import DecisionEngine
from src.engine.range_matcher import COMBO_WEIGHTS
from src.engine.range_modifier import ACTION_KEYS, RangeContext, build_action_ranges


BASE_RANGE = "22+, A2s+, K9s+, QTs+, ATo+, KJo+"
LATENCY_LIMIT_SECONDS = 0.020


def _combination_count(ranges: dict[str, dict[str, float]]) -> float:
    return sum(
        COMBO_WEIGHTS[combo] * frequency / 100.0
        for action_range in ranges.values()
        for combo, frequency in action_range.items()
    )


def _build(context: RangeContext) -> dict[str, dict[str, float]]:
    return build_action_ranges({"push": BASE_RANGE}, context=context)


def test_bubble_icm_tightens_normal_range() -> None:
    normal = _build(RangeContext(icm_stage="NORMAL"))
    bubble = _build(RangeContext(icm_stage="BUBBLE"))

    assert _combination_count(bubble) < _combination_count(normal)


def test_ante_expands_range_by_weighted_combinations() -> None:
    without_ante = _build(RangeContext(has_ante=False, table_size=9))
    with_ante = _build(RangeContext(has_ante=True, table_size=9))

    assert _combination_count(with_ante) > _combination_count(without_ante)


def test_opponent_style_changes_range_dynamically() -> None:
    tight = _build(RangeContext(opponent_style="TIGHT"))
    loose = _build(RangeContext(opponent_style="LOOSE"))

    assert _combination_count(tight) < _combination_count(loose)


def test_action_ranges_are_valid_normalized_matrix_cells() -> None:
    ranges = build_action_ranges(
        {
            "push": "TT+, AKs, AKo",
            "raise": "88+, AJs+, AQo+",
            "isolate": "66+, ATs+, KQs, AJo+",
            "call": "22+, A2s+, K9s+, QTs+, ATo+, KJo+",
        },
        context=RangeContext(has_ante=True, opponent_style="LOOSE"),
    )

    assert tuple(ranges) == ACTION_KEYS
    for action_range in ranges.values():
        assert set(action_range) <= set(COMBO_WEIGHTS)
        assert all(0 < frequency <= 100 for frequency in action_range.values())
    for combo in COMBO_WEIGHTS:
        assert (
            round(
                sum(action_range.get(combo, 0.0) for action_range in ranges.values()), 2
            )
            <= 100.0
        )
    assert any(
        sum(combo in action_range for action_range in ranges.values()) > 1
        for combo in COMBO_WEIGHTS
    )


@pytest.fixture
def populated_session() -> Session:
    database = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(database)
    with Session(database) as session:
        session.add_all(
            [
                NashPushFold(
                    table_size=9,
                    position="UTG",
                    stack_bb=10,
                    has_ante=True,
                    action="PUSH_ONLY",
                    range_str=BASE_RANGE,
                ),
                FacingActionRange(
                    hero_position="CO",
                    villain_position="MP",
                    villain_action="OPEN_2.5X",
                    stack_bb=30,
                    opponent_style="REG",
                    range_3bet_push="TT+, AKs",
                    range_3bet_raise="AJs+, KQs, JJ-99",
                    range_call="ATs, KJs, QJs, 88-66",
                ),
                PostflopStrategy(
                    pot_type="SRP",
                    hero_role="PFR",
                    hero_position="IP",
                    texture_id="DRY_RAINBOW",
                    bucket_id="TPTK",
                    stack_depth="MEDIUM",
                    action_check_pct=25,
                    action_bet_pct=75,
                    action_raise_pct=0,
                    recommended_sizing="BET_33%_POT",
                ),
            ]
        )
        session.commit()
        yield session
    database.dispose()


@pytest.mark.parametrize("decision_kind", ["first_in", "facing_action", "postflop"])
def test_decision_latency_is_below_20_ms(
    populated_session: Session, decision_kind: str
) -> None:
    engine = DecisionEngine()
    calls = {
        "first_in": lambda: engine.get_preflop_first_in_decision(
            populated_session, 9, "UTG", 10, "AJs"
        ),
        "facing_action": lambda: engine.get_preflop_facing_action_decision(
            populated_session, "CO", "MP", "OPEN_2.5X", 30, "REG", "AJs"
        ),
        "postflop": lambda: engine.get_postflop_decision(
            populated_session, "AsKs", "Kc7d2h"
        ),
    }
    call = calls[decision_kind]
    call()  # Exclude one-time SQL compilation and cache population.

    samples = []
    for _ in range(50):
        started = perf_counter()
        result = call()
        samples.append(perf_counter() - started)
        assert result.is_fallback is False

    p95 = sorted(samples)[int(len(samples) * 0.95) - 1]
    assert p95 < LATENCY_LIMIT_SECONDS, (
        f"{decision_kind} p95 latency was {p95 * 1000:.2f} ms "
        f"(median {median(samples) * 1000:.2f} ms)"
    )
