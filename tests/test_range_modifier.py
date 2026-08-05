from __future__ import annotations

import pytest

from src.engine.range_matcher import COMBO_WEIGHTS, TOTAL_COMBINATIONS
from src.engine.range_modifier import (
    ACTION_KEYS,
    RangeContext,
    action_frequencies,
    ante_expansion,
    build_action_ranges,
    hand_vs_range_equity,
    icm_coefficient,
    mixed_frequencies,
    modify_range,
    MIN_DISPLAY_FREQUENCY,
    WIDE_TEMPERATURE,
)


def test_ante_expands_range_from_dead_money() -> None:
    no_ante = RangeContext(has_ante=False)
    with_ante = RangeContext(has_ante=True, table_size=9, ante_bb=0.125)
    assert ante_expansion(no_ante) == 0
    assert 0.02 <= ante_expansion(with_ante) <= 0.05
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


def test_boundary_region_has_monotonic_mixed_frequencies() -> None:
    modified = modify_range(
        "77+, ATs+", action="raise", context=RangeContext(has_ante=True)
    )
    frequencies = list(modified.combos.values())
    assert frequencies == sorted(frequencies, reverse=True)
    assert sum(0 < frequency < 100 for frequency in frequencies) > 1
    assert frequencies[0] > frequencies[-1]


@pytest.mark.parametrize(
    ("score", "thresholds", "temperature"),
    [
        (50.0, [("call", 40.0), ("raise", 55.0), ("push", 70.0)], 4.0),
        (12.5, [("raise", 12.5)], 9.0),
        (90.0, [("push", 60.0)], 4.0),
    ],
)
def test_mixed_frequencies_sum_to_100(score, thresholds, temperature) -> None:
    assert round(sum(mixed_frequencies(score, thresholds, temperature).values()), 2) == 100.0


def test_mixed_frequencies_far_from_threshold_is_near_binary() -> None:
    above = mixed_frequencies(77.0, [("push", 60.0)], 4.0)
    below = mixed_frequencies(43.0, [("push", 60.0)], 4.0)

    assert above["push"] > 98
    assert below["fold"] > 98


def test_mixed_frequencies_at_threshold_is_near_50_50() -> None:
    frequencies = mixed_frequencies(60.0, [("raise", 60.0)], 4.0)

    assert 45 <= frequencies["fold"] <= 55
    assert 45 <= frequencies["raise"] <= 55


def test_temperature_affects_mixing_width() -> None:
    cold = mixed_frequencies(68.0, [("raise", 60.0)], 4.0)
    warm = mixed_frequencies(68.0, [("raise", 60.0)], 9.0)

    assert cold["raise"] > warm["raise"]


def test_action_ranges_respect_min_display_frequency() -> None:
    ranges = build_action_ranges({"raise": "JJ+"})

    assert all(
        frequency > MIN_DISPLAY_FREQUENCY
        for action_range in ranges.values()
        for frequency in action_range.values()
    )


def test_range_stats_match_actual_frequencies() -> None:
    modified = modify_range("77+, ATs+", action="raise")
    actual = sum(
        COMBO_WEIGHTS[combo] * frequency / 100.0
        for combo, frequency in modified.combos.items()
    )

    assert modified.combinations == round(actual, 2)
    assert modified.percentage == round(actual * 100.0 / TOTAL_COMBINATIONS, 2)


def test_action_frequencies_include_fold_remainder() -> None:
    ranges = build_action_ranges({"raise": "77+, ATs+"})
    combo = next(iter(ranges["raise"]))
    frequencies = action_frequencies(combo, ranges)

    assert sum(frequencies.values()) == 100.0
    assert WIDE_TEMPERATURE > 0
