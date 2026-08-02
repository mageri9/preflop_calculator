"""Runtime composition of opponent preflop action sequences."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.db.models import FacingActionRange, IcmPushFold, LimpCallRange, LimpRange, NashPushFold, OpenRange
from src.engine.position_utils import blinds_and_antes_bb, position_risk
from src.engine.range_matcher import COMBO_WEIGHTS, get_combo_equity
from src.engine.range_modifier import (
    ACTION_KEYS,
    MIN_DISPLAY_FREQUENCY,
    RangeContext,
    action_frequencies,
    hand_vs_range_equity,
    mixed_frequencies,
    modify_range,
    resolve_temperature,
)

ActionType = Literal["LIMP", "OPEN", "CALL", "THREE_BET", "PUSH"]
POSITION_ORDER = ("UTG", "UTG+1", "MP", "MP+1", "HJ", "CO", "BTN", "BTN/SB", "SB", "BB")
OPEN_BB = 2.5
THREE_BET_MULTIPLIER = 3.0
SHOVE_MARGIN_PCT = 5.0


@dataclass(frozen=True, slots=True)
class ActionEvent:
    position: str
    action: ActionType


@dataclass(frozen=True, slots=True)
class PotState:
    pot_bb: float
    cost_to_call_bb: float


@dataclass(slots=True)
class MultiwayResult:
    action: str
    is_in_range: bool
    range_str: str | None
    pot_bb: float
    cost_to_call_bb: float
    equity_pct: float | None
    pot_odds_pct: float
    villain_link_ranges: list[dict[str, Any]]
    details: dict[str, Any]


def _nearest_by_stack(session: Session, model: type[Any], stack_bb: float, **filters: Any) -> Any:
    statement = select(model)
    for name, value in filters.items():
        statement = statement.where(getattr(model, name) == value)
    return session.scalar(statement.order_by(func.abs(model.stack_bb - stack_bb)))


def validate_action_sequence(events: Sequence[ActionEvent]) -> None:
    if not events:
        raise ValueError("action_sequence must contain at least one event")
    if len(events) > 6:
        raise ValueError("action_sequence cannot contain more than 6 events")
    positions = [event.position.strip().upper() for event in events]
    if len(set(positions)) != len(positions):
        raise ValueError("Positions in action_sequence must not repeat")
    try:
        order = [POSITION_ORDER.index(position) for position in positions]
    except ValueError as exc:
        raise ValueError("Unsupported position in action_sequence") from exc
    if order != sorted(order):
        raise ValueError("Positions must follow preflop action order")
    if events[0].action in {"CALL", "THREE_BET"}:
        raise ValueError(f"{events[0].action} cannot be the first action")
    aggressive_seen = False
    three_bet_seen = False
    for index, event in enumerate(events):
        if event.action == "CALL" and not any(
            previous.action in {"LIMP", "OPEN", "PUSH", "THREE_BET"}
            for previous in events[:index]
        ):
            raise ValueError("CALL requires a preceding action")
        if event.action == "THREE_BET":
            if not aggressive_seen or three_bet_seen:
                raise ValueError("THREE_BET requires one preceding OPEN or PUSH; 4-bets are unsupported")
            three_bet_seen = True
        elif event.action == "PUSH":
            if not aggressive_seen:
                aggressive_seen = True
            elif not three_bet_seen:
                three_bet_seen = True
            else:
                raise ValueError("More than two aggressive actions are unsupported")
        elif event.action == "OPEN":
            if aggressive_seen:
                raise ValueError("Only one opening aggressive action is supported")
            aggressive_seen = True


def resolve_link_range(db: Session, event: ActionEvent, stack_bb: float, opponent_style: str,
                       *, preceding_action: ActionType | None = None, hero_position: str = "BB",
                       preceding_position: str | None = None,
                       table_size: int = 9, icm_stage: str = "NORMAL", has_ante: bool = True) -> str | None:
    if event.action == "OPEN":
        row = _nearest_by_stack(db, OpenRange, stack_bb, position=event.position, style=opponent_style)
        return row.range_str if row else None

    if event.action == "LIMP":
        row = _nearest_by_stack(db, LimpRange, stack_bb, position=event.position, style=opponent_style)
        return row.range_str if row else None

    if event.action == "CALL" and preceding_action == "LIMP":
        row = _nearest_by_stack(db, LimpCallRange, stack_bb, position=event.position, style=opponent_style)
        return row.range_str if row else None

    if event.action == "PUSH" and preceding_action is None:
        model = NashPushFold if icm_stage == "NORMAL" else IcmPushFold
        filters: dict[str, Any] = {"table_size": table_size, "position": event.position,
                                   "has_ante": has_ante, "action": "PUSH_ONLY"}
        if model is IcmPushFold:
            filters["payout_stage"] = icm_stage
        row = _nearest_by_stack(db, model, stack_bb, **filters)
        return row.range_str if row else None

    villain_action = "PUSH" if preceding_action == "PUSH" else "LIMP" if preceding_action == "LIMP" else "OPEN_2.5X"
    row = _nearest_by_stack(db, FacingActionRange, stack_bb, hero_position=event.position,
                            villain_position=preceding_position or _preceding_position(db, event, hero_position),
                            villain_action=villain_action, opponent_style=opponent_style)
    if not row:
        return None

    if event.action in {"THREE_BET", "PUSH"}:
        return (
            row.range_3bet_push
            if stack_bb <= 20 and row.range_3bet_push
            else (row.range_3bet_raise or row.range_3bet_push or row.range_call)
        )

    return row.range_call


def _preceding_position(db: Session, event: ActionEvent, fallback: str) -> str:
    del db
    index = POSITION_ORDER.index(event.position)
    return POSITION_ORDER[max(0, index - 1)] if index else fallback


def compute_pot_state(action_sequence: Sequence[ActionEvent], stack_bb: float,
                      has_ante: bool, table_size: int) -> PotState:
    pot = blinds_and_antes_bb(table_size, has_ante)
    current_bet = 1.0
    for event in action_sequence:
        if event.action == "LIMP": contribution = 1.0
        elif event.action == "OPEN": contribution = current_bet = OPEN_BB
        elif event.action == "THREE_BET": contribution = current_bet = min(stack_bb, current_bet * THREE_BET_MULTIPLIER)
        elif event.action == "PUSH": contribution = current_bet = stack_bb
        else: contribution = current_bet
        pot += contribution
    return PotState(round(pot, 2), round(current_bet, 2))


def hero_vs_field_equity(hero_combo: str, villain_ranges: Sequence[Mapping[str, float]]) -> float:
    if not villain_ranges:
        return get_combo_equity(hero_combo)

    equities = [hand_vs_range_equity(hero_combo, v_range) for v_range in villain_ranges]
    base_equity = sum(equities) / len(equities) if equities else get_combo_equity(hero_combo)

    num_opponents = len(villain_ranges)
    if num_opponents > 1:
        multiway_penalty = (num_opponents - 1) * 7.5
        base_equity = max(5.0, base_equity - multiway_penalty)

    return round(base_equity, 2)


def hero_vs_field_equity_v2(hero_combo: str, villain_ranges: Sequence[Mapping[str, float]]) -> float:
    """TODO: blocker-aware joint survival equity; intentionally not wired in MVP."""
    return hero_vs_field_equity(hero_combo, villain_ranges)


def build_multiway_action_ranges(
    villain_ranges: Sequence[Mapping[str, float]],
    *,
    call_threshold: float,
    push_threshold: float,
    context: RangeContext,
    stack_bb: float,
    can_push: bool,
) -> dict[str, dict[str, float]]:
    """Build mixed hero actions from equity thresholds against the full field."""

    result: dict[str, dict[str, float]] = {key: {} for key in ACTION_KEYS}
    if not villain_ranges:
        return result
    ordered_actions = [("call", call_threshold)]
    if can_push:
        ordered_actions.append(("push", max(call_threshold, push_threshold)))
    temperature = resolve_temperature(context, "shove" if stack_bb <= 20 else "wide")
    for combo in COMBO_WEIGHTS:
        score = hero_vs_field_equity(combo, villain_ranges)
        frequencies = mixed_frequencies(score, ordered_actions, temperature)
        for action, _ in ordered_actions:
            frequency = frequencies[action]
            if frequency > MIN_DISPLAY_FREQUENCY:
                result[action][combo] = frequency
    return result


def resolve_multiway_decision(db: Session, hero_position: str, action_sequence: Sequence[ActionEvent],
                              stack_bb: float, table_size: int, icm_stage: str, has_ante: bool,
                              opponent_style: str, hero_combo: str | None = None) -> MultiwayResult:
    validate_action_sequence(action_sequence)
    links: list[dict[str, Any]] = []
    weighted_ranges: list[Mapping[str, float]] = []
    warnings: list[str] = []
    # Calls do not become the action being faced by later players. Keep the
    # latest initiating/aggressive event as the lookup anchor across callers.
    anchor: ActionEvent | None = None
    for event in action_sequence:
        base = resolve_link_range(db, event, stack_bb, opponent_style,
                                  preceding_action=anchor.action if anchor else None,
                                  preceding_position=anchor.position if anchor else None,
                                  hero_position=hero_position, table_size=table_size,
                                  icm_stage=icm_stage, has_ante=has_ante)
        if not base:
            warnings.append(f"No range found for {event.position} {event.action}")
        else:
            modified = modify_range(base, action="call" if event.action == "CALL" else "raise",
                                    context=RangeContext(table_size=table_size, icm_stage=icm_stage,
                                                         has_ante=has_ante, opponent_style=opponent_style,
                                                         position_risk=position_risk(table_size, event.position)))
            weighted_ranges.append(modified.combos)
            links.append({"position": event.position, "action": event.action,
                          "range_str": modified.range_str, "combinations": modified.combinations})
        if event.action in {"OPEN", "PUSH", "THREE_BET"} or (
            event.action == "LIMP" and anchor is None
        ):
            anchor = event
    pot = compute_pot_state(action_sequence, stack_bb, has_ante, table_size)
    odds = round(100 * pot.cost_to_call_bb / (pot.pot_bb + pot.cost_to_call_bb), 2)
    equity = hero_vs_field_equity(hero_combo, weighted_ranges) if hero_combo else None

    num_opponents = max(1, len(weighted_ranges))
    multiway_margin = SHOVE_MARGIN_PCT + (num_opponents - 1) * 3.0
    call_margin = (num_opponents - 1) * 1.5

    can_push = not any(event.action == "PUSH" for event in action_sequence)
    hero_context = RangeContext(
        table_size=table_size,
        icm_stage=icm_stage,
        has_ante=has_ante,
        opponent_style=opponent_style,
        position_risk=position_risk(table_size, hero_position),
    )
    matrix_action_ranges = build_multiway_action_ranges(
        weighted_ranges,
        call_threshold=odds + call_margin,
        push_threshold=odds + multiway_margin,
        context=hero_context,
        stack_bb=stack_bb,
        can_push=can_push,
    )
    if hero_combo:
        frequencies = action_frequencies(hero_combo, matrix_action_ranges)
        action = max(
            (("PUSH", frequencies["push"]), ("CALL", frequencies["call"]),
             ("FOLD", frequencies["fold"])),
            key=lambda item: item[1],
        )[0]
    else:
        action = "DEFEND"

    aggregate = min(links, key=lambda item: item["combinations"])["range_str"] if links else None
    return MultiwayResult(action, bool(hero_combo and action != "FOLD"), aggregate, pot.pot_bb,
                          pot.cost_to_call_bb, equity, odds, links,
                          {"warnings": warnings, "action_ranges": matrix_action_ranges,
                           "temperature": resolve_temperature(
                               hero_context, "shove" if stack_bb <= 20 else "wide"
                           )})
