"""Tests for preflop range expansion and matching."""

import pytest

from src.engine.range_matcher import (
    expand_range_str,
    get_range_stats,
    is_combo_in_range,
    normalize_combo,
)


@pytest.mark.parametrize(("combo", "expected"), [("JAs", "AJs"), ("KAo", "AKo")])
def test_normalize_combo_orders_ranks(combo: str, expected: str) -> None:
    assert normalize_combo(combo) == expected


@pytest.mark.parametrize(
    ("range_str", "expected"),
    [
        ("77+", {"77", "88", "99", "TT", "JJ", "QQ", "KK", "AA"}),
        ("JJ-99", {"99", "TT", "JJ"}),
        ("ATs+", {"ATs", "AJs", "AQs", "AKs"}),
    ],
)
def test_expand_range_str(range_str: str, expected: set[str]) -> None:
    assert expand_range_str(range_str) == expected


def test_is_combo_in_range() -> None:
    assert is_combo_in_range("AJs", "77+, ATs+") is True
    assert is_combo_in_range("AJo", "77+, ATs+") is False


def test_get_range_stats() -> None:
    stats = get_range_stats("77+, ATs+")

    assert stats == {"combos_count": 64, "percentage": 4.83, "total_matrix_cells": 12}
