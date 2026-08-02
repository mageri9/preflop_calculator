from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import src.engine.multiway_resolver as multiway_resolver
from src.db.seed_data import seed_tournament_data
from src.engine.multiway_resolver import (
    ActionEvent,
    compute_pot_state,
    resolve_link_range,
    resolve_multiway_decision,
    validate_action_sequence,
)
from src.engine.range_matcher import COMBO_WEIGHTS
from src.engine.range_modifier import action_frequencies


def test_sequence_validation() -> None:
    validate_action_sequence([ActionEvent("UTG", "OPEN"), ActionEvent("CO", "CALL")])
    validate_action_sequence([ActionEvent("UTG", "OPEN"), ActionEvent("CO", "THREE_BET")])
    with pytest.raises(ValueError, match="first"):
        validate_action_sequence([ActionEvent("UTG", "CALL")])
    with pytest.raises(ValueError, match="order"):
        validate_action_sequence([ActionEvent("CO", "OPEN"), ActionEvent("UTG", "CALL")])
    with pytest.raises(ValueError, match="repeat"):
        validate_action_sequence([ActionEvent("UTG", "LIMP"), ActionEvent("UTG", "CALL")])
    with pytest.raises(ValueError, match="more than 6"):
        validate_action_sequence([ActionEvent(position, "LIMP") for position in
                                  ("UTG", "UTG+1", "MP", "MP+1", "HJ", "CO", "BTN")])


def test_pot_state_scenarios() -> None:
    state = compute_pot_state(
        [ActionEvent("UTG", "LIMP"), ActionEvent("MP", "LIMP"), ActionEvent("CO", "OPEN")],
        40, False, 9,
    )
    assert state.pot_bb == 6.0
    assert state.cost_to_call_bb == 2.5
    state = compute_pot_state(
        [ActionEvent("UTG", "OPEN"), ActionEvent("MP", "CALL"),
         ActionEvent("HJ", "CALL"), ActionEvent("CO", "THREE_BET")], 40, False, 9,
    )
    assert state.pot_bb == 16.5
    assert state.cost_to_call_bb == 7.5


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    factory = sessionmaker(bind=engine)
    seed_tournament_data(factory, engine)
    with factory() as session:
        yield session


def test_each_link_uses_its_reference_table(db) -> None:
    assert resolve_link_range(db, ActionEvent("UTG", "LIMP"), 30, "REG")
    assert resolve_link_range(db, ActionEvent("UTG", "OPEN"), 30, "REG")
    assert resolve_link_range(db, ActionEvent("UTG", "PUSH"), 10, "REG", table_size=9)
    assert resolve_link_range(db, ActionEvent("MP", "CALL"), 30, "REG",
                              preceding_action="LIMP", preceding_position="UTG")
    assert resolve_link_range(db, ActionEvent("CO", "THREE_BET"), 30, "REG",
                              preceding_action="OPEN", preceding_position="UTG")


def test_resolver_returns_pot_equity_and_modified_links(db) -> None:
    result = resolve_multiway_decision(
        db, "BB", [ActionEvent("UTG", "OPEN"), ActionEvent("CO", "CALL")],
        30, 9, "NORMAL", True, "REG", "AJs",
    )
    assert result.pot_bb > 1.5
    assert result.cost_to_call_bb == 2.5
    assert result.equity_pct is not None
    assert len(result.villain_link_ranges) == 2


def test_callers_do_not_replace_original_aggressor_lookup_anchor(db, monkeypatch) -> None:
    lookups: list[tuple[str, str | None, str | None]] = []
    original = multiway_resolver.resolve_link_range

    def recording_lookup(*args, **kwargs):
        event = args[1]
        lookups.append((event.action, kwargs.get("preceding_action"), kwargs.get("preceding_position")))
        return original(*args, **kwargs)

    monkeypatch.setattr(multiway_resolver, "resolve_link_range", recording_lookup)
    resolve_multiway_decision(
        db, "BB",
        [ActionEvent("UTG", "OPEN"), ActionEvent("MP", "CALL"),
         ActionEvent("HJ", "CALL"), ActionEvent("CO", "THREE_BET")],
        40, 9, "NORMAL", False, "REG", "AJs",
    )

    assert lookups[1:] == [
        ("CALL", "OPEN", "UTG"),
        ("CALL", "OPEN", "UTG"),
        ("THREE_BET", "OPEN", "UTG"),
    ]


def test_each_link_receives_ante_and_icm_modifiers(db) -> None:
    events = [ActionEvent("UTG", "OPEN"), ActionEvent("CO", "CALL")]
    baseline = resolve_multiway_decision(db, "BB", events, 30, 9, "NORMAL", False, "REG")
    with_ante = resolve_multiway_decision(db, "BB", events, 30, 9, "NORMAL", True, "REG")
    with_icm = resolve_multiway_decision(db, "BB", events, 30, 9, "BUBBLE", False, "REG")

    assert all(
        modified["combinations"] > base["combinations"]
        for base, modified in zip(baseline.villain_link_ranges, with_ante.villain_link_ranges)
    )
    assert all(
        modified["combinations"] < base["combinations"]
        for base, modified in zip(baseline.villain_link_ranges, with_icm.villain_link_ranges)
    )


def test_missing_link_is_a_warning_not_an_exception(db) -> None:
    result = resolve_multiway_decision(
        db, "BB", [ActionEvent("BB", "LIMP")], 30, 9, "NORMAL", False, "REG", "AA",
    )
    assert result.details["warnings"]


def test_push_reshove_call_sequence(db) -> None:
    events = [
        ActionEvent("UTG", "PUSH"),
        ActionEvent("BTN", "PUSH"),
        ActionEvent("SB", "CALL"),
        ActionEvent("BB", "CALL"),
    ]
    validate_action_sequence(events)
    result = resolve_multiway_decision(db, "BB", events, 10, 9, "NORMAL", True, "REG")
    assert result.pot_bb > 10.0
    assert len(result.villain_link_ranges) == 4
    assert not result.details["action_ranges"]["push"]


def test_multiway_matrix_contains_normalized_mixed_frequencies(db) -> None:
    result = resolve_multiway_decision(
        db, "BB", [ActionEvent("UTG", "OPEN"), ActionEvent("CO", "CALL")],
        30, 9, "NORMAL", True, "REG", "22",
    )
    ranges = result.details["action_ranges"]

    assert ranges["push"] and ranges["call"]
    assert any(combo in ranges["push"] and combo in ranges["call"] for combo in COMBO_WEIGHTS)
    for combo in COMBO_WEIGHTS:
        assert sum(action_frequencies(combo, ranges).values()) == 100.0


def test_multiway_uses_stack_and_icm_temperature(db) -> None:
    events = [ActionEvent("UTG", "OPEN"), ActionEvent("CO", "CALL")]
    short = resolve_multiway_decision(db, "BB", events, 20, 9, "NORMAL", True, "REG")
    deep = resolve_multiway_decision(db, "BB", events, 30, 9, "NORMAL", True, "REG")
    icm = resolve_multiway_decision(db, "BB", events, 30, 9, "BUBBLE", True, "REG")

    assert short.details["temperature"] == 4.0
    assert deep.details["temperature"] == 9.0
    assert icm.details["temperature"] == 7.65


def test_multiway_strong_hand_remains_near_deterministic(db) -> None:
    result = resolve_multiway_decision(
        db, "BB", [ActionEvent("UTG", "OPEN"), ActionEvent("CO", "CALL")],
        10, 9, "NORMAL", True, "REG", "AA",
    )
    frequencies = action_frequencies("AA", result.details["action_ranges"])

    assert result.action == "PUSH"
    assert frequencies["push"] > 98
