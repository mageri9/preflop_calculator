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


def normalize_combo(combo: str) -> str:
    """Return a canonical starting-hand token, ordered from high rank to low.

    Pairs use two ranks (for example, ``TT``). Non-pairs must include a suitedness
    suffix, ``s`` or ``o`` (for example, ``AJs`` and ``AKo``).

    Raises:
        ValueError: If *combo* is not a valid matrix cell.
    """
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
    """Expand a normalized ``+`` token towards stronger hands."""
    if len(token) == 2:
        start = _RANK_VALUE[token[0]]
        return {rank * 2 for rank in RANKS[start:]}

    high, low, suffix = token
    high_index = _RANK_VALUE[high]
    low_index = _RANK_VALUE[low]
    return {f"{high}{rank}{suffix}" for rank in RANKS[low_index:high_index]}


def _expand_dash(start: str, end: str) -> set[str]:
    """Expand an inclusive range between two normalized compatible endpoints."""
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
    """Expand a comma-separated range notation string into canonical matrix cells.

    Supported forms are individual cells (``KQs``), plus ranges (``77+``,
    ``ATs+``), and inclusive dash ranges (``JJ-99``).

    Raises:
        ValueError: If the range string contains an invalid token.
    """
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
    """Return whether *combo* is included in *range_str*.

    An absent or whitespace-only range never matches.
    """
    if not range_str or not range_str.strip():
        return False
    return normalize_combo(combo) in expand_range_str(range_str)


def get_range_stats(range_str: str) -> dict[str, Any]:
    """Return exact combination count, percentage, and occupied matrix cells."""
    expanded = expand_range_str(range_str)
    combos_count = sum(COMBO_WEIGHTS[combo] for combo in expanded)
    return {
        "combos_count": combos_count,
        "percentage": round(combos_count / TOTAL_COMBINATIONS * 100, 2),
        "total_matrix_cells": len(expanded),
    }
