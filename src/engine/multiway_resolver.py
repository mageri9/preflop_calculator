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


def is_offsuit_non_premium(combo: str) -> bool:
    if combo.endswith("o"):
        if combo in ("AKo", "AQo"):
            return False
        return True
    return False


def hero_vs_field_equity(hero_combo: str, villain_ranges: Sequence[Mapping[str, float]]) -> float:
    if not villain_ranges:
        return get_combo_equity(hero_combo)

    equities = [hand_vs_range_equity(hero_combo, v_range) for v_range in villain_ranges]
    base_equity = sum(equities) / len(equities) if equities else get_combo_equity(hero_combo)

    num_opponents = len(villain_ranges)
    if num_opponents > 1:
        multiway_penalty = (num_opponents - 1) * 7.5
        base_equity = max(5.0, base_equity - multiway_penalty)

        if is_offsuit_non_premium(hero_combo):
            eqr_discount = 0.18 + (num_opponents - 1) * 0.04
            base_equity = base_equity * (1.0 - eqr_discount)

    return round(max(5.0, base_equity), 2)


def build_multiway_action_ranges(
    villain_ranges: Sequence[Mapping[str, float]],
    *,
    call_threshold: float,
    push_threshold: float | None = None,
    aggressive_action: Literal["push", "raise", "isolate"] = "push",
    aggressive_threshold: float | None = None,
    context: RangeContext,
    stack_bb: float,
    can_push: bool = True,
) -> dict[str, dict[str, float]]:
    """Build mixed hero actions from equity thresholds against the full field."""

    result: dict[str, dict[str, float]] = {key: {} for key in ACTION_KEYS}
    if not villain_ranges:
        return result

    eff_agg_threshold = aggressive_threshold if aggressive_threshold is not None else (
        push_threshold if push_threshold is not None else call_threshold + 10.0
    )

    ordered_actions: list[tuple[str, float]] = [("call", call_threshold)]
    if can_push:
        ordered_actions.append((aggressive_action, max(call_threshold, eff_agg_threshold)))

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
    is_facing_push = any(event.action == "PUSH" for event in action_sequence)
    has_three_bet = any(event.action == "THREE_BET" for event in action_sequence)
    open_count = sum(1 for e in action_sequence if e.action == "OPEN")
    call_count = sum(1 for e in action_sequence if e.action == "CALL")
    limp_count = sum(1 for e in action_sequence if e.action == "LIMP")
    has_aggressive = open_count > 0 or has_three_bet or is_facing_push
    is_facing_limp = not has_aggressive and limp_count > 0

    can_raise = pot.cost_to_call_bb < stack_bb

    # Повышаем требуемый запас эквити для колла и рейза в мультипотах:
    call_margin = 3.0 + (num_opponents - 1) * 3.0
    call_threshold = odds + call_margin

    if stack_bb <= 20.0 or is_facing_push:
        aggressive_action: Literal["push", "raise", "isolate"] = "push"
        push_margin = (
            22.0 + (num_opponents - 1) * 5.0
        )
        aggressive_threshold = odds + push_margin
    elif is_facing_limp:
        aggressive_action = "isolate"
        isolate_margin = (
            14.0 + (num_opponents - 1) * 4.0
        )
        aggressive_threshold = odds + isolate_margin
    else:
        aggressive_action = "raise"
        raise_margin = (
            22.0 + (num_opponents - 1) * 5.0
        )
        aggressive_threshold = odds + raise_margin

    hero_context = RangeContext(
        table_size=table_size,
        icm_stage=icm_stage,
        has_ante=has_ante,
        opponent_style=opponent_style,
        position_risk=position_risk(table_size, hero_position),
    )
    matrix_action_ranges = build_multiway_action_ranges(
        weighted_ranges,
        call_threshold=call_threshold,
        aggressive_action=aggressive_action,
        aggressive_threshold=aggressive_threshold,
        context=hero_context,
        stack_bb=stack_bb,
        can_push=can_raise,
    )
    if hero_combo:
        frequencies = action_frequencies(hero_combo, matrix_action_ranges)

        call_label = "CHECK" if hero_position == "BB" and is_facing_limp else "CALL"

        if not can_raise:
            options: list[tuple[str, str]] = [(call_label, "call")]
        elif aggressive_action == "push":
            if has_three_bet:
                agg_label = "4BET_PUSH"
            elif open_count >= 1 and call_count >= 1:
                agg_label = "SQUEEZE_PUSH"
            elif has_aggressive:
                agg_label = "3BET_PUSH"
            else:
                agg_label = "PUSH"
            options = [(agg_label, "push"), (call_label, "call")]
        elif aggressive_action == "isolate":
            options = [("ISOLATE", "isolate"), (call_label, "call")]
        else:
            if has_three_bet:
                agg_label = "4BET_RAISE"
            elif open_count >= 1 and call_count >= 1:
                agg_label = "SQUEEZE"
            else:
                agg_label = "3BET_RAISE"
            options = [(agg_label, "raise"), (call_label, "call")]

        selected_action, selected_key = max(
            options,
            key=lambda option: frequencies[option[1]],
        )

        if frequencies[selected_key] >= frequencies["fold"]:
            action = selected_action
        else:
            action = "FOLD"
    else:
        action = "DEFEND"

    aggregate = min(links, key=lambda item: item["combinations"])["range_str"] if links else None
    return MultiwayResult(action, bool(hero_combo and action != "FOLD"), aggregate, pot.pot_bb,
                          pot.cost_to_call_bb, equity, odds, links,
                          {"warnings": warnings, "action_ranges": matrix_action_ranges,
                           "temperature": resolve_temperature(
                               hero_context, "shove" if stack_bb <= 20 else "wide"
                           )})