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
from src.engine.range_matcher import (
    get_combo_equity,
    get_range_equity,
    get_range_stats,
    is_combo_in_range,
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


class DecisionEngine:

    @staticmethod
    def _range_result(
        *,
        action: str,
        hero_combo: Optional[str],
        range_str: str,
        details: dict[str, Any],
        frequencies: Optional[dict[str, Any]] = None,
    ) -> DecisionResult:
        in_range = is_combo_in_range(hero_combo, range_str) if hero_combo else False
        equity = get_combo_equity(hero_combo) if hero_combo else get_range_equity(range_str)

        if frequencies is None:
            if action in ("PUSH", "3BET_PUSH"):
                frequencies = {"PUSH": 100 if (in_range or not hero_combo) else 0, "FOLD": 0 if (in_range or not hero_combo) else 100}
            elif action == "OPEN_RAISE":
                frequencies = {"RAISE": 80 if (in_range or not hero_combo) else 0, "PUSH": 20 if (in_range or not hero_combo) else 0, "FOLD": 0 if (in_range or not hero_combo) else 100}
            elif action == "ISOLATE":
                frequencies = {"ISOLATE": 80 if (in_range or not hero_combo) else 0, "CALL": 20 if (in_range or not hero_combo) else 0, "FOLD": 0 if (in_range or not hero_combo) else 100}
            elif action in ("3BET_RAISE", "RAISE"):
                frequencies = {"RAISE": 70 if (in_range or not hero_combo) else 0, "CALL": 30 if (in_range or not hero_combo) else 0, "FOLD": 0 if (in_range or not hero_combo) else 100}
            elif action == "CALL":
                frequencies = {"CALL": 100 if (in_range or not hero_combo) else 0, "FOLD": 0 if (in_range or not hero_combo) else 100}
            else:
                frequencies = {"FOLD": 100}

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
        )

    @staticmethod
    def _fallback(action: str, details: dict[str, Any], equity_pct: float = 30.0) -> DecisionResult:
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
                row = session.scalar(
                    select(OpenRange)
                    .where(
                        OpenRange.position == hero_position,
                        OpenRange.style == opponent_style,
                    )
                    .order_by(func.abs(OpenRange.stack_bb - stack_bb))
                )
                if row is None:
                    return self._fallback("FOLD", details, get_combo_equity(hero_combo) if hero_combo else 40.0)

                in_range = is_combo_in_range(hero_combo, row.range_str) if hero_combo else True
                freqs = {"RAISE": 85, "PUSH": 15, "FOLD": 0} if in_range else {"RAISE": 0, "PUSH": 0, "FOLD": 100}
                return self._range_result(
                    action="OPEN_RAISE",
                    hero_combo=hero_combo,
                    range_str=row.range_str,
                    details=details,
                    frequencies=freqs,
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
                return self._fallback("FOLD", details, get_combo_equity(hero_combo) if hero_combo else 35.0)

            details["strategy_stack_bb"] = row.stack_bb
            in_range = is_combo_in_range(hero_combo, row.range_str) if hero_combo else True
            freqs = {"PUSH": 100, "FOLD": 0} if in_range else {"PUSH": 0, "FOLD": 100}
            return self._range_result(
                action="PUSH",
                hero_combo=hero_combo,
                range_str=row.range_str,
                details=details,
                frequencies=freqs,
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
    ) -> DecisionResult:
        details: dict[str, Any] = {
            "hero_position": hero_position,
            "villain_position": villain_position,
            "villain_action": villain_action,
            "stack_bb": stack_bb,
            "opponent_style": opponent_style,
        }
        try:
            row = session.scalar(
                select(FacingActionRange)
                .where(
                    FacingActionRange.hero_position == hero_position,
                    FacingActionRange.villain_position == villain_position,
                    FacingActionRange.villain_action == villain_action,
                    FacingActionRange.opponent_style == opponent_style,
                )
                .order_by(func.abs(FacingActionRange.stack_bb - stack_bb))
            )
            if row is None:
                return self._fallback("FOLD", details, get_combo_equity(hero_combo) if hero_combo else 30.0)

            details["strategy_stack_bb"] = row.stack_bb
            if hero_combo:
                action_options = (
                    ("3BET_PUSH", row.range_3bet_push),
                    ("ISOLATE" if villain_action == "LIMP" else "3BET_RAISE", row.range_3bet_raise),
                    ("CALL", row.range_call),
                )
                for action, range_str in action_options:
                    if range_str and is_combo_in_range(hero_combo, range_str):
                        freqs = {}
                        if action == "3BET_PUSH":
                            freqs = {"PUSH": 100, "RAISE": 0, "CALL": 0, "FOLD": 0}
                        elif action == "ISOLATE":
                            freqs = {"ISOLATE": 80, "CALL": 20, "FOLD": 0}
                        elif action == "3BET_RAISE":
                            freqs = {"RAISE": 70, "CALL": 30, "FOLD": 0}
                        elif action == "CALL":
                            freqs = {"CALL": 100, "FOLD": 0}

                        return self._range_result(
                            action=action,
                            hero_combo=hero_combo,
                            range_str=range_str,
                            details=details,
                            frequencies=freqs,
                        )
                return DecisionResult(
                    action="FOLD",
                    is_in_range=False,
                    range_str=None,
                    range_stats=None,
                    recommended_sizing=None,
                    frequencies={"FOLD": 100, "CALL": 0, "RAISE": 0},
                    equity_pct=get_combo_equity(hero_combo),
                    is_fallback=False,
                    details=details,
                )
            else:
                combined_ranges = [r for r in (row.range_3bet_push, row.range_3bet_raise, row.range_call) if r]
                combined_str = ", ".join(combined_ranges) if combined_ranges else None
                freqs = {"ISOLATE": 30, "CALL": 50, "FOLD": 20} if villain_action == "LIMP" else {"RAISE": 25, "CALL": 45, "FOLD": 30}
                return DecisionResult(
                    action="DEFEND",
                    is_in_range=False,
                    range_str=combined_str,
                    range_stats=get_range_stats(combined_str) if combined_str else None,
                    recommended_sizing=None,
                    frequencies=freqs,
                    equity_pct=get_range_equity(combined_str) if combined_str else 45.0,
                    is_fallback=False,
                    details=details,
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
                "CHECK": row.action_check_pct,
                "BET": row.action_bet_pct,
                "RAISE": row.action_raise_pct,
            }
            action = max(
                (("CHECK", frequencies["CHECK"]), ("BET", frequencies["BET"]), ("RAISE", frequencies["RAISE"])),
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