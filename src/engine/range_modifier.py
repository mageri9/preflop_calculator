"""Lightweight dynamic modifiers for preflop ranges and frequencies.

The module operates on the 169 canonical starting-hand cells.  It deliberately
does not query storage or depend on the API layer, so the decision engine can
apply it to database-backed base ranges without changing their representation.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from math import exp
from collections.abc import Callable
from typing import Final, Literal, Mapping

from src.engine.range_matcher import (
    COMBO_WEIGHTS,
    PREFLOP_EQUITIES,
    TOTAL_COMBINATIONS,
    expand_range_str,
    normalize_combo,
)

ACTION_KEYS: Final[tuple[str, ...]] = ("push", "raise", "isolate", "call")
SHOVE_TEMPERATURE: Final[float] = 2.5
WIDE_TEMPERATURE: Final[float] = 3.5
ICM_TEMPERATURE_FACTOR: Final[float] = 0.85
MIN_DISPLAY_FREQUENCY: Final[float] = 1.0
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
    return 0.02 + 0.03 * share


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
    """Apply range modifiers and smooth the resulting boundary with a sigmoid."""

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

    score_fn = lambda combo: _ranking_equity(combo, villain_range)
    ranked = sorted(COMBO_WEIGHTS, key=score_fn, reverse=True)
    threshold = _threshold_from_target(ranked, target, score_fn)
    temperature = resolve_temperature(context, "wide")
    selected = {
        combo: frequency
        for combo in ranked
        if (frequency := round(_sigmoid(score_fn(combo), threshold, temperature) * 100.0, 2))
        >= MIN_DISPLAY_FREQUENCY
    }
    combinations = sum(
        COMBO_WEIGHTS[combo] * frequency / 100.0
        for combo, frequency in selected.items()
    )

    return WeightedRange(
        combos=selected,
        range_str=", ".join(selected),
        combinations=round(combinations, 2),
        percentage=round(combinations * 100.0 / TOTAL_COMBINATIONS, 2),
    )


def build_action_ranges(
    base_ranges: Mapping[str, str | None],
    *,
    context: RangeContext = RangeContext(),
    villain_range: str | Mapping[str, float] | None = None,
    bluff_actions: frozenset[str] = frozenset(),
    spot_kind: Literal["shove", "wide"] = "wide",
) -> dict[str, dict[str, float]]:
    """Build mutually normalized mixed frequencies for every matrix cell."""

    result: dict[str, dict[str, float]] = {key: {} for key in ACTION_KEYS}
    action_targets: dict[str, float] = {}
    score_fn = lambda combo: _ranking_equity(combo, villain_range)
    for action in ACTION_KEYS:
        base_range = base_ranges.get(action)
        if not base_range:
            continue
        base = expand_range_str(base_range)
        factor = (1.0 + ante_expansion(context)) * icm_coefficient(
            context.icm_stage, context.position_risk
        )
        factor *= opponent_coefficient(
            context.opponent_style, action, bluff=action in bluff_actions
        )
        target = _clamp(
            sum(COMBO_WEIGHTS[combo] for combo in base) * factor,
            0.0,
            float(TOTAL_COMBINATIONS),
        )
        if target <= 0:
            continue
        action_targets[action] = target

    ordered_names = [
        action
        for action in ("call", "isolate", "raise", "push")
        if action in action_targets
    ]
    ranked = sorted(COMBO_WEIGHTS, key=score_fn, reverse=True)
    thresholds: dict[str, float] = {}
    cumulative_target = 0.0
    for action in reversed(ordered_names):
        cumulative_target = min(
            float(TOTAL_COMBINATIONS), cumulative_target + action_targets[action]
        )
        thresholds[action] = _threshold_from_target(ranked, cumulative_target, score_fn)
    ordered = [(action, thresholds[action]) for action in ordered_names]
    temperature = resolve_temperature(context, spot_kind)
    for combo in COMBO_WEIGHTS:
        frequencies = mixed_frequencies(score_fn(combo), ordered, temperature)
        for action in ordered_names:
            frequency = frequencies[action]
            if frequency > MIN_DISPLAY_FREQUENCY:
                result[action][combo] = frequency
    return result


def action_frequencies(
    hero_combo: str,
    action_ranges: Mapping[str, Mapping[str, float]],
) -> dict[str, float]:
    """Extract a combo's dynamic matrix mix and assign the remainder to fold."""

    combo = normalize_combo(hero_combo)
    frequencies = {
        key: round(_clamp(float(action_ranges.get(key, {}).get(combo, 0.0)), 0.0, 100.0), 2)
        for key in ACTION_KEYS
    }
    frequencies["fold"] = round(max(0.0, 100.0 - sum(frequencies.values())), 2)
    return frequencies


def resolve_temperature(
    context: RangeContext, spot_kind: Literal["shove", "wide"]
) -> float:
    """Resolve mixing width from stack regime and ICM pressure."""

    base = SHOVE_TEMPERATURE if spot_kind == "shove" else WIDE_TEMPERATURE
    icm_factor = ICM_TEMPERATURE_FACTOR if context.icm_stage != "NORMAL" else 1.0
    return round(base * icm_factor, 2)


def mixed_frequencies(
    score: float,
    ordered_actions: list[tuple[str, float]],
    temperature: float,
) -> dict[str, float]:
    """Return a normalized ordinal-logit distribution over fold and actions."""

    if temperature <= 0:
        raise ValueError("temperature must be positive")
    monotonic: list[tuple[str, float]] = []
    previous = float("-inf")
    for name, threshold in ordered_actions:
        threshold = max(float(threshold), previous)
        monotonic.append((name, threshold))
        previous = threshold
    cdf = [1.0, *(_sigmoid(score, threshold, temperature) for _, threshold in monotonic), 0.0]
    names = ["fold", *(name for name, _ in monotonic)]
    raw = [max(0.0, cdf[index] - cdf[index + 1]) for index in range(len(names))]
    return _normalize_to_100(dict(zip(names, raw)))


def _threshold_from_target(
    ranked_combos: list[str],
    target_weight: float,
    score_fn: Callable[[str], float],
) -> float:
    """Convert a weighted range size into the score of its boundary cell."""

    if not ranked_combos:
        raise ValueError("ranked_combos must not be empty")
    scores = [score_fn(combo) for combo in ranked_combos]
    total_weight = sum(COMBO_WEIGHTS[combo] for combo in ranked_combos)
    if target_weight <= 0:
        return max(scores) + 10.0
    if target_weight >= total_weight:
        return min(scores) - 10.0
    accumulated = 0.0
    index = 0
    while index < len(ranked_combos):
        score = score_fn(ranked_combos[index])
        end = index
        group_weight = 0.0
        while end < len(ranked_combos) and score_fn(ranked_combos[end]) == score:
            group_weight += COMBO_WEIGHTS[ranked_combos[end]]
            end += 1
        if accumulated + group_weight >= target_weight:
            fill = (target_weight - accumulated) / group_weight
            stronger = score_fn(ranked_combos[index - 1]) if index else score + 10.0
            weaker = score_fn(ranked_combos[end]) if end < len(ranked_combos) else score - 10.0
            upper = (stronger + score) / 2.0
            lower = (score + weaker) / 2.0
            return upper + (lower - upper) * fill
        accumulated += group_weight
        index = end
    return min(scores) - 10.0


def _sigmoid(score: float, threshold: float, temperature: float) -> float:
    exponent = _clamp(-(score - threshold) / temperature, -700.0, 700.0)
    return _clamp(1.0 / (1.0 + exp(exponent)), 0.0, 1.0)


def _normalize_to_100(probabilities: Mapping[str, float]) -> dict[str, float]:
    if not probabilities:
        return {}
    total = sum(max(0.0, value) for value in probabilities.values())
    if total <= 0:
        first = next(iter(probabilities))
        return {key: 100.0 if key == first else 0.0 for key in probabilities}
    rounded = {
        key: round(max(0.0, value) * 100.0 / total, 2)
        for key, value in probabilities.items()
    }
    diff = round(100.0 - sum(rounded.values()), 2)
    largest = max(rounded, key=rounded.get)
    rounded[largest] = round(rounded[largest] + diff, 2)
    return rounded


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
