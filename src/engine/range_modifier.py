"""Lightweight dynamic modifiers for preflop ranges and frequencies.

The module operates on the 169 canonical starting-hand cells.  It deliberately
does not query storage or depend on the API layer, so the decision engine can
apply it to database-backed base ranges without changing their representation.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from math import exp
from typing import Final, Mapping

from src.engine.range_matcher import (
    COMBO_WEIGHTS,
    PREFLOP_EQUITIES,
    TOTAL_COMBINATIONS,
    expand_range_str,
    normalize_combo,
)

ACTION_KEYS: Final[tuple[str, ...]] = ("push", "raise", "isolate", "call")
ICM_BASE: Final[dict[str, float]] = {
    "NORMAL": 1.0,
    "BUBBLE": 0.725,
    "FINAL_TABLE": 0.825,
    "PAY_JUMP": 0.775,
}


@dataclass(frozen=True, slots=True)
class RangeContext:
    """External conditions used to modify a stored base range."""

    has_ante: bool = False
    table_size: int = 9
    ante_bb: float = 0.125
    icm_stage: str = "NORMAL"
    opponent_style: str = "REG"
    position_risk: float = 0.5


@dataclass(frozen=True, slots=True)
class WeightedRange:
    """A modified range where values are action frequencies in percent."""

    combos: Mapping[str, float]
    range_str: str
    combinations: float
    percentage: float


def ante_expansion(context: RangeContext) -> float:
    """Return a 5-10% expansion derived from ante dead money."""

    if not context.has_ante:
        return 0.0
    players = max(2, min(10, context.table_size))
    dead_money = players * max(0.0, context.ante_bb)
    share = dead_money / (1.5 + dead_money)
    return 0.05 + 0.05 * share


def icm_coefficient(stage: str, position_risk: float = 0.5) -> float:
    """Calculate ICM compression; higher position risk tightens the range."""

    normalized = stage.strip().upper()
    if normalized not in ICM_BASE:
        raise ValueError(f"Unsupported ICM stage: {stage!r}")
    base = ICM_BASE[normalized]
    if base == 1.0:
        return base
    risk = _clamp(position_risk, 0.0, 1.0)
    # The requested stage interval is reached at the two risk extremes.
    return round(_clamp(base + (0.5 - risk) * 0.05, 0.70, 1.0), 4)


def opponent_coefficient(style: str, action: str, *, bluff: bool = False) -> float:
    """Return a style adjustment specific to the intended action."""

    style = style.strip().upper()
    action = action.strip().lower()
    if style not in {"TIGHT", "REG", "LOOSE"}:
        raise ValueError(f"Unsupported opponent style: {style!r}")
    if action not in ACTION_KEYS:
        raise ValueError(f"Unsupported range action: {action!r}")
    if style == "REG":
        return 1.0
    if style == "TIGHT":
        return 1.12 if action in {"push", "raise", "isolate"} and bluff else 0.90
    if bluff:
        return 0.0
    return 1.12 if action in {"push", "raise", "call"} else 1.05


def hand_vs_range_equity(hero_combo: str, villain_range: str | Mapping[str, float]) -> float:
    """Estimate hero equity against a weighted 169-cell opponent range.

    Pairwise results are derived from the relative preflop strengths, rather
    than reusing equity versus a random hand.  Card-removal reduces the weight
    of villain cells sharing hero ranks.
    """

    hero = normalize_combo(hero_combo)
    weights = _range_weights(villain_range)
    total = 0.0
    equity_sum = 0.0
    for villain, frequency in weights.items():
        available = _unblocked_weight(hero, villain)
        weight = available * _clamp(float(frequency), 0.0, 100.0) / 100.0
        if weight <= 0:
            continue
        equity_sum += _pairwise_equity(hero, villain) * weight
        total += weight
    if total == 0:
        raise ValueError("Villain range has no available combinations")
    return round(equity_sum / total, 2)


def modify_range(
    base_range: str,
    *,
    action: str,
    context: RangeContext = RangeContext(),
    villain_range: str | Mapping[str, float] | None = None,
    bluff: bool = False,
) -> WeightedRange:
    """Apply ante, ICM and opponent factors and calculate boundary mixes."""

    action = action.strip().lower()
    base = expand_range_str(base_range)
    if not base:
        return WeightedRange({}, "", 0.0, 0.0)

    factor = (1.0 + ante_expansion(context)) * icm_coefficient(
        context.icm_stage, context.position_risk
    )
    factor *= opponent_coefficient(context.opponent_style, action, bluff=bluff)
    base_weight = sum(COMBO_WEIGHTS[combo] for combo in base)
    target = _clamp(base_weight * factor, 0.0, float(TOTAL_COMBINATIONS))

    ranked_base = sorted(
        base, key=lambda combo: _ranking_equity(combo, villain_range), reverse=True
    )
    if factor <= 1.0:
        ranked = ranked_base
    else:
        ranked_outside = sorted(
            (combo for combo in COMBO_WEIGHTS if combo not in base),
            key=lambda combo: _ranking_equity(combo, villain_range),
            reverse=True,
        )
        ranked = [*ranked_base, *ranked_outside]
    selected: dict[str, float] = {}
    accumulated = 0.0
    for combo in ranked:
        cell_weight = COMBO_WEIGHTS[combo]
        remaining = target - accumulated
        if remaining <= 0:
            break
        frequency = min(100.0, 100.0 * remaining / cell_weight)
        selected[combo] = round(frequency, 2)
        accumulated += cell_weight * frequency / 100.0

    return WeightedRange(
        combos=selected,
        range_str=", ".join(selected),
        combinations=round(accumulated, 2),
        percentage=round(accumulated * 100.0 / TOTAL_COMBINATIONS, 2),
    )


def build_action_ranges(
    base_ranges: Mapping[str, str | None],
    *,
    context: RangeContext = RangeContext(),
    villain_range: str | Mapping[str, float] | None = None,
    bluff_actions: frozenset[str] = frozenset(),
) -> dict[str, dict[str, float]]:
    """Return the stable four-colour matrix payload expected by the frontend."""

    result: dict[str, dict[str, float]] = {key: {} for key in ACTION_KEYS}
    claimed: set[str] = set()
    for action in ACTION_KEYS:
        base_range = base_ranges.get(action)
        if not base_range:
            continue
        modified = modify_range(
            base_range,
            action=action,
            context=context,
            villain_range=villain_range,
            bluff=action in bluff_actions,
        )
        # Higher-priority actions own overlapping matrix cells.
        result[action] = {
            combo: frequency
            for combo, frequency in modified.combos.items()
            if combo not in claimed
        }
        claimed.update(result[action])
    return result


def action_frequencies(
    hero_combo: str,
    action_ranges: Mapping[str, Mapping[str, float]],
) -> dict[str, float]:
    """Extract a combo's dynamic matrix mix and assign the remainder to fold."""

    combo = normalize_combo(hero_combo)
    frequencies = {key: 0.0 for key in ACTION_KEYS}
    remaining = 100.0
    for action in ACTION_KEYS:
        frequency = _clamp(float(action_ranges.get(action, {}).get(combo, 0.0)), 0.0, remaining)
        frequencies[action] = round(frequency, 2)
        remaining -= frequency
    frequencies["fold"] = round(remaining, 2)
    return frequencies


def _range_weights(range_value: str | Mapping[str, float]) -> dict[str, float]:
    if isinstance(range_value, str):
        return {combo: 100.0 for combo in expand_range_str(range_value)}
    return {normalize_combo(combo): float(weight) for combo, weight in range_value.items()}


def _ranking_equity(combo: str, villain_range: str | Mapping[str, float] | None) -> float:
    return hand_vs_range_equity(combo, villain_range) if villain_range else PREFLOP_EQUITIES[combo]


@lru_cache(maxsize=169 * 169)
def _pairwise_equity(hero: str, villain: str) -> float:
    if hero == villain:
        return 50.0
    difference = PREFLOP_EQUITIES[hero] - PREFLOP_EQUITIES[villain]
    equity = 100.0 / (1.0 + exp(-difference / 8.5))
    return _clamp(equity, 5.0, 95.0)


def _unblocked_weight(hero: str, villain: str) -> float:
    weight = float(COMBO_WEIGHTS[villain])
    for rank in set(hero[:2]):
        occurrences = villain[:2].count(rank)
        if occurrences:
            weight *= (4 - hero[:2].count(rank)) / 4
    return weight


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
