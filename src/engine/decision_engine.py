"""Database-backed preflop and postflop poker decision service."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.db.models import (
    FacingActionRange,
    IcmPushFold,
    NashPushFold,
    OpenRange,
    PostflopStrategy,
)
from src.engine.postflop_evaluator import evaluate_postflop
from src.engine.multiway_resolver import ActionEvent, _nearest_by_stack, resolve_multiway_decision
from src.engine.range_matcher import (
    get_combo_equity,
    get_range_equity,
    get_range_stats,
    is_combo_in_range,
)
from src.engine.range_modifier import (
    ACTION_KEYS,
    RangeContext,
    action_frequencies,
    build_action_ranges,
    hand_vs_range_equity,
)

POSTFLOP_BUCKET_EQUITY = {
    "MONSTER": 88.5,
    "TPTK": 74.0,
    "TPGK": 65.0,
    "WEAK_PAIR": 48.0,
    "NUT_DRAW": 52.0,
    "GUTSHOT": 34.0,
    "AIR": 18.0,
}

@dataclass(slots=True)
class DecisionResult:
    action: str
    is_in_range: bool
    range_str: Optional[str]
    range_stats: Optional[dict[str, Any]]
    recommended_sizing: Optional[str]
    frequencies: Optional[dict[str, Any]]
    equity_pct: Optional[float] = None
    is_fallback: bool = False
    details: dict[str, Any] = field(default_factory=dict)
    action_ranges: dict[str, dict[str, float]] = field(
        default_factory=lambda: {key: {} for key in ACTION_KEYS}
    )


class DecisionEngine:

    def get_preflop_multiway_decision(
        self, session: Session, hero_position: str, action_sequence: list[ActionEvent],
        stack_bb: float, table_size: int, icm_stage: str, has_ante: bool,
        opponent_style: str, hero_combo: Optional[str] = None,
    ) -> DecisionResult:
        details: dict[str, Any] = {
            "hero_position": hero_position, "stack_bb": stack_bb,
            "action_sequence": [{"position": e.position, "action": e.action} for e in action_sequence],
        }
        try:
            result = resolve_multiway_decision(
                session, hero_position, action_sequence, stack_bb, table_size,
                icm_stage, has_ante, opponent_style, hero_combo,
            )
            details.update(result.details)
            details.update({"pot_bb": result.pot_bb, "cost_to_call_bb": result.cost_to_call_bb,
                            "pot_odds_pct": result.pot_odds_pct,
                            "villain_link_ranges": result.villain_link_ranges})
            if not result.villain_link_ranges:
                return self._fallback("FOLD", details, result.equity_pct)
            return DecisionResult(
                action=result.action, is_in_range=result.is_in_range, range_str=result.range_str,
                range_stats=get_range_stats(result.range_str) if result.range_str else None,
                recommended_sizing=None, frequencies=None, equity_pct=result.equity_pct,
                is_fallback=bool(result.details.get("warnings")), details=details,
                action_ranges={key: {} for key in ACTION_KEYS},
            )
        except Exception as exc:
            details["error"] = str(exc)
            return self._fallback("FOLD", details, get_combo_equity(hero_combo) if hero_combo else None)

    @staticmethod
    def _range_result(
        *,
        action: str,
        hero_combo: Optional[str],
        range_str: str,
        details: dict[str, Any],
        frequencies: Optional[dict[str, Any]] = None,
        action_ranges: Optional[dict[str, dict[str, float]]] = None,
        equity_pct: Optional[float] = None,
    ) -> DecisionResult:
        in_range = is_combo_in_range(hero_combo, range_str) if hero_combo else False
        equity = equity_pct
        if equity is None:
            equity = get_combo_equity(hero_combo) if hero_combo else get_range_equity(range_str)

        action_ranges = action_ranges or {key: {} for key in ACTION_KEYS}
        if frequencies is None and hero_combo:
            frequencies = action_frequencies(hero_combo, action_ranges)
        elif frequencies is None:
            frequencies = None

        return DecisionResult(
            action=action if (in_range or hero_combo is None) else "FOLD",
            is_in_range=in_range,
            range_str=range_str,
            range_stats=get_range_stats(range_str),
            recommended_sizing=None,
            frequencies=frequencies,
            equity_pct=equity,
            is_fallback=False,
            details=details,
            action_ranges=action_ranges,
        )

    @staticmethod
    def _fallback(
        action: str, details: dict[str, Any], equity_pct: Optional[float] = None
    ) -> DecisionResult:
        return DecisionResult(
            action=action,
            is_in_range=False,
            range_str=None,
            range_stats=None,
            recommended_sizing="CHECK" if action == "CHECK" else None,
            frequencies={"FOLD": 100} if action == "FOLD" else {"CHECK": 100},
            equity_pct=equity_pct,
            is_fallback=True,
            details=details,
            action_ranges={key: {} for key in ACTION_KEYS},
        )

    @staticmethod
    def _position(table_size: int, position: str) -> str:
        """Map aliases to labels available in seeded ranges, without indexing past seats."""
        position = (position or "").strip().upper()
        if table_size == 2 and position in {"BTN", "SB", "BTN/SB"}:
            return "BTN/SB"
        return position

    @staticmethod
    def _facing_position(table_size: int, position: str) -> str:
        """Map the combined heads-up button label to the defense dataset alias."""
        normalized = (position or "").strip().upper()
        return "BTN" if table_size == 2 and normalized == "BTN/SB" else normalized

    @staticmethod
    def _ranges(base_ranges: dict[str, Optional[str]], *, table_size: int, icm_stage: str,
                has_ante: bool, opponent_style: str, position_risk: float = 0.5):
        return build_action_ranges(
            base_ranges,
            context=RangeContext(table_size=max(2, min(9, table_size)), icm_stage=icm_stage,
                                 has_ante=has_ante, opponent_style=opponent_style,
                                 position_risk=position_risk),
            bluff_actions=(
                frozenset({"push", "raise", "isolate"})
                if opponent_style.strip().upper() == "TIGHT"
                else frozenset()
            ),
        )

    def get_preflop_first_in_decision(
        self,
        session: Session,
        table_size: int,
        hero_position: str,
        stack_bb: float,
        hero_combo: Optional[str] = None,
        icm_stage: str = "NORMAL",
        has_ante: bool = True,
        opponent_style: str = "REG",
    ) -> DecisionResult:
        table_size = max(2, min(9, table_size))
        hero_position = self._position(table_size, hero_position)
        details: dict[str, Any] = {
            "table_size": table_size,
            "hero_position": hero_position,
            "stack_bb": stack_bb,
            "icm_stage": icm_stage,
            "has_ante": has_ante,
            "opponent_style": opponent_style,
        }
        try:
            if stack_bb > 15.0:
                row = _nearest_by_stack(
                    session, OpenRange, stack_bb, position=hero_position, style=opponent_style
                )
                if row is None:
                    return self._fallback("FOLD", details, get_combo_equity(hero_combo) if hero_combo else None)

                action_ranges = self._ranges(
                    {"raise": row.range_str}, table_size=table_size, icm_stage=icm_stage,
                    has_ante=has_ante, opponent_style=opponent_style,
                )
                return self._range_result(
                    action="OPEN_RAISE",
                    hero_combo=hero_combo,
                    range_str=", ".join(action_ranges["raise"]),
                    details=details,
                    action_ranges=action_ranges,
                )

            model: type[NashPushFold] | type[IcmPushFold]
            statement: Any
            if icm_stage == "NORMAL":
                model = NashPushFold
                statement = select(model).where(
                    model.table_size == table_size,
                    model.position == hero_position,
                    model.has_ante == has_ante,
                    model.action == "PUSH_ONLY",
                )
            else:
                model = IcmPushFold
                statement = select(model).where(
                    model.table_size == table_size,
                    model.position == hero_position,
                    model.payout_stage == icm_stage,
                    model.has_ante == has_ante,
                    model.action == "PUSH_ONLY",
                )
            row = session.scalar(statement.order_by(func.abs(model.stack_bb - stack_bb)))

            if row is None and has_ante:
                fallback_statement = select(model).where(
                    model.table_size == table_size,
                    model.position == hero_position,
                    model.has_ante.is_(False),
                    model.action == "PUSH_ONLY",
                )
                if icm_stage != "NORMAL":
                    fallback_statement = fallback_statement.where(model.payout_stage == icm_stage)
                row = session.scalar(
                    fallback_statement.order_by(func.abs(model.stack_bb - stack_bb))
                )
                if row is not None:
                    details["used_ante_fallback"] = True

            if row is None:
                return self._fallback("FOLD", details, get_combo_equity(hero_combo) if hero_combo else None)

            details["strategy_stack_bb"] = row.stack_bb
            action_ranges = self._ranges(
                {"push": row.range_str}, table_size=table_size, icm_stage=icm_stage,
                has_ante=has_ante, opponent_style=opponent_style,
            )
            return self._range_result(
                action="PUSH",
                hero_combo=hero_combo,
                range_str=", ".join(action_ranges["push"]),
                details=details,
                action_ranges=action_ranges,
            )
        except Exception as exc:
            details["error"] = str(exc)
            return self._fallback("FOLD", details)

    def get_preflop_facing_action_decision(
        self,
        session: Session,
        hero_position: str,
        villain_position: str,
        villain_action: str,
        stack_bb: float,
        opponent_style: str,
        hero_combo: Optional[str] = None,
        table_size: int = 9,
        icm_stage: str = "NORMAL",
        has_ante: bool = True,
    ) -> DecisionResult:
        table_size = max(2, min(9, table_size))
        hero_position = self._facing_position(table_size, hero_position)
        villain_position = self._facing_position(table_size, villain_position)
        details: dict[str, Any] = {
            "hero_position": hero_position,
            "villain_position": villain_position,
            "villain_action": villain_action,
            "stack_bb": stack_bb,
            "opponent_style": opponent_style,
            "table_size": table_size,
            "icm_stage": icm_stage,
            "has_ante": has_ante,
        }
        try:
            row = _nearest_by_stack(
                session, FacingActionRange, stack_bb, hero_position=hero_position,
                villain_position=villain_position, villain_action=villain_action,
                opponent_style=opponent_style,
            )
            if row is None:
                return self._fallback("FOLD", details, get_combo_equity(hero_combo) if hero_combo else None)

            # Передаем отдельные поддиапазоны в details
            details["strategy_stack_bb"] = row.stack_bb
            details["range_3bet_push"] = row.range_3bet_push
            details["range_3bet_raise"] = row.range_3bet_raise
            details["range_call"] = row.range_call

            raise_key = "isolate" if villain_action == "LIMP" else "raise"
            action_ranges = self._ranges(
                {"push": row.range_3bet_push, raise_key: row.range_3bet_raise,
                 "call": row.range_call},
                table_size=table_size, icm_stage=icm_stage, has_ante=has_ante,
                opponent_style=opponent_style,
            )

            villain_open = _nearest_by_stack(
                session, OpenRange, stack_bb, position=villain_position, style=opponent_style
            )
            hero_equity = None
            if hero_combo and villain_open is not None:
                hero_equity = hand_vs_range_equity(hero_combo, villain_open.range_str)
                details["equity_source"] = f"{villain_position} {opponent_style} range"

            if hero_combo:
                action_options = (
                    ("3BET_PUSH", "push"),
                    ("ISOLATE" if villain_action == "LIMP" else "3BET_RAISE", raise_key),
                    ("CALL", "call"),
                )
                for action, range_key in action_options:
                    range_str = ", ".join(action_ranges[range_key])
                    if range_str and is_combo_in_range(hero_combo, range_str):
                        return self._range_result(
                            action=action,
                            hero_combo=hero_combo,
                            range_str=range_str,
                            details=details,
                            action_ranges=action_ranges,
                            equity_pct=hero_equity,
                        )
                return DecisionResult(
                    action="FOLD",
                    is_in_range=False,
                    range_str=None,
                    range_stats=None,
                    recommended_sizing=None,
                    frequencies=action_frequencies(hero_combo, action_ranges),
                    equity_pct=hero_equity if hero_equity is not None else get_combo_equity(hero_combo),
                    is_fallback=False,
                    details=details,
                    action_ranges=action_ranges,
                )
            else:
                combined_ranges = [", ".join(action_ranges[key]) for key in ACTION_KEYS if action_ranges[key]]
                combined_str = ", ".join(combined_ranges) if combined_ranges else None
                return DecisionResult(
                    action="DEFEND",
                    is_in_range=False,
                    range_str=combined_str,
                    range_stats=get_range_stats(combined_str) if combined_str else None,
                    recommended_sizing=None,
                    frequencies=None,
                    equity_pct=get_range_equity(combined_str) if combined_str else None,
                    is_fallback=False,
                    details=details,
                    action_ranges=action_ranges,
                )
        except Exception as exc:
            details["error"] = str(exc)
            return self._fallback("FOLD", details)

    def get_postflop_decision(
        self,
        session: Session,
        hero_cards: list[str] | str,
        flop_cards: list[str] | str,
        pot_type: str = "SRP",
        hero_role: str = "PFR",
        hero_position: str = "IP",
        stack_bb: float = 30.0,
    ) -> DecisionResult:
        details: dict[str, Any] = {
            "pot_type": pot_type,
            "hero_role": hero_role,
            "hero_position": hero_position,
            "stack_bb": stack_bb,
        }
        try:
            evaluation = evaluate_postflop(hero_cards, flop_cards)
            stack_depth = "SHORT" if stack_bb <= 25 else "MEDIUM" if stack_bb <= 50 else "DEEP"
            details.update(evaluation)
            details["stack_depth"] = stack_depth
            row = session.scalar(
                select(PostflopStrategy).where(
                    PostflopStrategy.pot_type == pot_type,
                    PostflopStrategy.hero_role == hero_role,
                    PostflopStrategy.hero_position == hero_position,
                    PostflopStrategy.texture_id == evaluation["texture_id"],
                    PostflopStrategy.bucket_id == evaluation["bucket_id"],
                    PostflopStrategy.stack_depth == stack_depth,
                )
            )
            equity_pct = POSTFLOP_BUCKET_EQUITY.get(evaluation["bucket_id"], 50.0)
            if row is None:
                return self._fallback("CHECK", details, equity_pct)

            frequencies = {
                "check_pct": row.action_check_pct,
                "bet_pct": row.action_bet_pct,
                "raise_pct": row.action_raise_pct,
            }
            action = max(
                (("CHECK", frequencies["check_pct"]), ("BET", frequencies["bet_pct"]),
                 ("RAISE", frequencies["raise_pct"])),
                key=lambda item: item[1],
            )[0]
            return DecisionResult(
                action=action,
                is_in_range=True,
                range_str=None,
                range_stats=None,
                recommended_sizing=row.recommended_sizing,
                frequencies=frequencies,
                equity_pct=equity_pct,
                is_fallback=False,
                details=details,
            )
        except Exception as exc:
            details["error"] = str(exc)
            return self._fallback("CHECK", details)
