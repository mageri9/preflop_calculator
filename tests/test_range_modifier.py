from __future__ import annotations

import pytest

from src.engine.range_modifier import (
    ACTION_KEYS,
    RangeContext,
    action_frequencies,
    ante_expansion,
    build_action_ranges,
    hand_vs_range_equity,
    icm_coefficient,
    modify_range,
)


def test_ante_expands_range_from_dead_money() -> None:
    no_ante = RangeContext(has_ante=False)
    with_ante = RangeContext(has_ante=True, table_size=9, ante_bb=0.125)

    assert ante_expansion(no_ante) == 0
    assert 0.05 <= ante_expansion(with_ante) <= 0.10
    assert modify_range("77+, ATs+", action="push", context=with_ante).combinations > modify_range(
        "77+, ATs+", action="push", context=no_ante
    ).combinations


def test_icm_coefficients_follow_stage_and_position_risk() -> None:
    assert icm_coefficient("NORMAL") == 1.0
    assert icm_coefficient("BUBBLE", 0) == 0.75
    assert icm_coefficient("BUBBLE", 1) == 0.70
    assert icm_coefficient("FINAL_TABLE", 0) == 0.85
    assert icm_coefficient("FINAL_TABLE", 1) == 0.80


def test_equity_is_calculated_against_actual_range() -> None:
    versus_tight = hand_vs_range_equity("AQo", "QQ+, AKs, AKo")
    versus_wide = hand_vs_range_equity("AQo", "22+, A2s+, K2s+, A2o+, K2o+")

    assert versus_tight < versus_wide
    assert hand_vs_range_equity("AA", "KK") > 50
    with pytest.raises(ValueError):
        hand_vs_range_equity("AA", {})


def test_loose_opponent_removes_pure_bluff_range() -> None:
    ranges = build_action_ranges(
        {"raise": "A5s-A2s", "call": "JJ+, AQs+, AKo"},
        context=RangeContext(opponent_style="LOOSE"),
        bluff_actions=frozenset({"raise"}),
    )

    assert tuple(ranges) == ACTION_KEYS
    assert ranges["raise"] == {}
    assert ranges["call"]


def test_boundary_cell_gets_computed_mix_and_frequency_remainder() -> None:
    modified = modify_range(
        "77+, ATs+", action="raise", context=RangeContext(has_ante=True)
    )
    boundary = next(combo for combo, frequency in modified.combos.items() if frequency < 100)
    payload = {key: {} for key in ACTION_KEYS}
    payload["raise"] = dict(modified.combos)

    frequencies = action_frequencies(boundary, payload)

    assert 0 < frequencies["raise"] < 100
    assert frequencies["raise"] + frequencies["fold"] == 100
