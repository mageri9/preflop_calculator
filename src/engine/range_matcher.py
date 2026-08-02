"""Utilities for expanding and matching standard preflop poker ranges."""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Final

RANKS: Final[str] = "23456789TJQKA"
TOTAL_COMBINATIONS: Final[int] = 1326
_RANK_VALUE: Final[dict[str, int]] = {rank: index for index, rank in enumerate(RANKS)}

# Every cell of the 13x13 starting-hand matrix maps to its suit realization count.
COMBO_WEIGHTS: Final[dict[str, int]] = {
    **{rank * 2: 6 for rank in RANKS},
    **{
        f"{high}{low}{suffix}": 4 if suffix == "s" else 12
        for high_index, high in enumerate(RANKS)
        for low in RANKS[:high_index]
        for suffix in ("s", "o")
    },
}

# Preflop equity vs 100% random hand for all 169 canonical starting hand combos
PREFLOP_EQUITIES: Final[dict[str, float]] = {
    "AA": 85.2, "KK": 82.4, "QQ": 79.9, "JJ": 77.5, "TT": 75.1, "99": 72.1, "88": 68.9, "77": 66.2, "66": 63.3, "55": 60.3, "44": 57.0, "33": 53.7, "22": 50.3,
    "AKs": 67.0, "AQs": 66.1, "AJs": 65.4, "ATs": 64.6, "A9s": 62.9, "A8s": 62.1, "A7s": 61.1, "A6s": 60.0, "A5s": 60.7, "A4s": 59.8, "A3s": 58.9, "A2s": 57.9,
    "KQs": 63.4, "KJs": 62.6, "KTs": 61.8, "K9s": 59.9, "K8s": 58.0, "K7s": 57.0, "K6s": 56.0, "K5s": 55.2, "K4s": 54.2, "K3s": 53.2, "K2s": 52.2,
    "QJs": 60.1, "QTs": 59.4, "Q9s": 57.5, "Q8s": 55.6, "Q7s": 53.7, "Q6s": 52.8, "Q5s": 51.9, "Q4s": 50.9, "Q3s": 49.9, "Q2s": 48.9,
    "JTs": 57.5, "J9s": 55.6, "J8s": 53.7, "J7s": 51.8, "J6s": 49.8, "J5s": 48.9, "J4s": 47.9, "J3s": 46.9, "J2s": 45.9,
    "T9s": 54.3, "T8s": 52.4, "T7s": 50.5, "T6s": 48.5, "T5s": 46.6, "T4s": 45.6, "T3s": 44.6, "T2s": 43.6,
    "98s": 50.9, "97s": 49.0, "96s": 47.1, "95s": 45.1, "94s": 43.1, "93s": 42.2, "92s": 41.2,
    "87s": 47.8, "86s": 45.8, "85s": 43.9, "84s": 41.9, "83s": 40.0, "82s": 39.0,
    "76s": 44.9, "75s": 42.9, "74s": 40.9, "73s": 39.0, "72s": 37.0,
    "65s": 42.1, "64s": 40.1, "63s": 38.1, "62s": 36.1,
    "54s": 39.8, "53s": 37.8, "52s": 35.8,
    "43s": 36.7, "42s": 34.6,
    "32s": 33.7,
    "AKo": 65.4, "AQo": 64.4, "AJo": 63.5, "ATo": 62.5, "A9o": 60.7, "A8o": 59.8, "A7o": 58.7, "A6o": 57.5, "A5o": 58.2, "A4o": 57.2, "A3o": 56.3, "A2o": 55.2,
    "KQo": 61.4, "KJo": 60.5, "KTo": 59.6, "K9o": 57.5, "K8o": 55.4, "K7o": 54.4, "K6o": 53.3, "K5o": 52.4, "K4o": 51.3, "K3o": 50.3, "K2o": 49.3,
    "QJo": 57.9, "QTo": 57.0, "Q9o": 54.9, "Q8o": 52.8, "Q7o": 50.8, "Q6o": 49.7, "Q5o": 48.8, "Q4o": 47.7, "Q3o": 46.6, "Q2o": 45.6,
    "JTo": 54.8, "J9o": 52.8, "J8o": 50.7, "J7o": 48.6, "J6o": 46.5, "J5o": 45.5, "J4o": 44.4, "J3o": 43.3, "J2o": 42.3,
    "T9o": 51.3, "T8o": 49.2, "T7o": 47.2, "T6o": 45.0, "T5o": 42.9, "T4o": 41.8, "T3o": 40.7, "T2o": 39.7,
    "98o": 47.6, "97o": 45.5, "96o": 43.4, "95o": 41.2, "94o": 39.1, "93o": 38.0, "92o": 36.9,
    "87o": 44.2, "86o": 42.1, "85o": 40.0, "84o": 37.8, "83o": 35.7, "82o": 34.6,
    "76o": 41.0, "75o": 38.9, "74o": 36.7, "73o": 34.6, "72o": 32.4,
    "65o": 38.0, "64o": 35.8, "63o": 33.7, "62o": 31.6,
    "54o": 35.4, "53o": 33.3, "52o": 31.2,
    "43o": 32.1, "42o": 29.9,
    "32o": 28.9,
}

def normalize_combo(combo: str) -> str:
    if not isinstance(combo, str):
        raise ValueError("Combo must be a string")

    token = combo.strip().upper()
    if len(token) == 2:
        first, second = token
        if first in RANKS and first == second:
            return token
    elif len(token) == 3:
        first, second, suitedness = token
        if (
            first in RANKS
            and second in RANKS
            and first != second
            and suitedness in {"S", "O"}
        ):
            high, low = sorted((first, second), key=_RANK_VALUE.__getitem__, reverse=True)
            return f"{high}{low}{suitedness.lower()}"

    raise ValueError(f"Invalid poker combo: {combo!r}")

def _expand_plus(token: str) -> set[str]:
    if len(token) == 2:
        start = _RANK_VALUE[token[0]]
        return {rank * 2 for rank in RANKS[start:]}

    high, low, suffix = token
    high_index = _RANK_VALUE[high]
    low_index = _RANK_VALUE[low]
    return {f"{high}{rank}{suffix}" for rank in RANKS[low_index:high_index]}

def _expand_dash(start: str, end: str) -> set[str]:
    if len(start) != len(end):
        raise ValueError(f"Incompatible range endpoints: {start}-{end}")

    if len(start) == 2:
        start_index = _RANK_VALUE[start[0]]
        end_index = _RANK_VALUE[end[0]]
        return {rank * 2 for rank in RANKS[min(start_index, end_index) : max(start_index, end_index) + 1]}

    if start[2] != end[2]:
        raise ValueError(f"Incompatible range endpoints: {start}-{end}")

    suffix = start[2]
    if start[0] == end[0]:
        high = start[0]
        low_indices = (_RANK_VALUE[start[1]], _RANK_VALUE[end[1]])
        return {
            f"{high}{rank}{suffix}"
            for rank in RANKS[min(low_indices) : max(low_indices) + 1]
            if rank != high
        }
    if start[1] == end[1]:
        low = start[1]
        high_indices = (_RANK_VALUE[start[0]], _RANK_VALUE[end[0]])
        return {
            normalize_combo(f"{rank}{low}{suffix}")
            for rank in RANKS[min(high_indices) : max(high_indices) + 1]
            if rank != low
        }

    raise ValueError(f"Range endpoints must share one rank: {start}-{end}")

@lru_cache(maxsize=2048)
def expand_range_str(range_str: str) -> set[str]:
    if not isinstance(range_str, str):
        raise ValueError("Range must be a string")

    expanded: set[str] = set()
    for raw_token in range_str.split(","):
        token = raw_token.strip()
        if not token:
            raise ValueError("Range contains an empty token")
        if token.endswith("+"):
            expanded.update(_expand_plus(normalize_combo(token[:-1])))
        elif "-" in token:
            if token.count("-") != 1:
                raise ValueError(f"Invalid range token: {token!r}")
            start, end = token.split("-")
            expanded.update(_expand_dash(normalize_combo(start), normalize_combo(end)))
        else:
            expanded.add(normalize_combo(token))
    return expanded

def is_combo_in_range(combo: str, range_str: str | None) -> bool:
    if not range_str or not range_str.strip():
        return False
    return normalize_combo(combo) in expand_range_str(range_str)

def get_combo_equity(combo: str) -> float:
    try:
        normalized = normalize_combo(combo)
        return PREFLOP_EQUITIES.get(normalized, 50.0)
    except ValueError:
        return 50.0

def get_range_equity(range_str: str) -> float:
    expanded = expand_range_str(range_str)
    if not expanded:
        return 50.0
    total_weight = sum(COMBO_WEIGHTS.get(combo, 1) for combo in expanded)
    if not total_weight:
        return 50.0
    weighted_equity = sum(PREFLOP_EQUITIES.get(combo, 50.0) * COMBO_WEIGHTS.get(combo, 1) for combo in expanded)
    return round(weighted_equity / total_weight, 1)

def get_range_stats(range_str: str) -> dict[str, Any]:
    expanded = expand_range_str(range_str)
    combos_count = sum(COMBO_WEIGHTS.get(combo, 1) for combo in expanded)
    return {
        "combos_count": combos_count,
        "total_matrix_cells": len(expanded),
    }