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
from src.engine.range_matcher import get_range_stats, is_combo_in_range


@dataclass(slots=True)
class DecisionResult:
    """A strategy recommendation together with the data used to produce it."""

    action: str
    is_in_range: bool
    range_str: Optional[str]
    range_stats: Optional[dict[str, Any]]
    recommended_sizing: Optional[str]
    frequencies: Optional[dict[str, int]]
    is_fallback: bool
    details: dict[str, Any] = field(default_factory=dict)


class DecisionEngine:
    """Resolve poker actions from the strategy tables with conservative fallbacks."""

    @staticmethod
    def _range_result(
        *,
        action: str,
        hero_combo: Optional[str],
        range_str: str,
        details: dict[str, Any],
    ) -> DecisionResult:
        in_range = is_combo_in_range(hero_combo, range_str) if hero_combo else False
        return DecisionResult(
            action=action if (in_range or hero_combo is None) else "FOLD",
            is_in_range=in_range,
            range_str=range_str,
            range_stats=get_range_stats(range_str),
            recommended_sizing=None,
            frequencies=None,
            is_fallback=False,
            details=details,
        )

    @staticmethod
    def _fallback(action: str, details: dict[str, Any]) -> DecisionResult:
        return DecisionResult(
            action=action,
            is_in_range=False,
            range_str=None,
            range_stats=None,
            recommended_sizing="CHECK" if action == "CHECK" else None,
            frequencies=None,
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
        """Return a push/fold or first-in open decision for the hero hand."""
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
                    select(OpenRange).where(
                        OpenRange.position == hero_position,
                        OpenRange.style == opponent_style,
                    )
                )
                if row is None:
                    return self._fallback("FOLD", details)
                return self._range_result(
                    action="OPEN_RAISE",
                    hero_combo=hero_combo,
                    range_str=row.range_str,
                    details=details,
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
                if icm_stage == "NORMAL":
                    fallback_statement = select(model).where(
                        model.table_size == table_size,
                        model.position == hero_position,
                        model.has_ante.is_(False),
                        model.action == "PUSH_ONLY",
                    )
                else:
                    fallback_statement = select(model).where(
                        model.table_size == table_size,
                        model.position == hero_position,
                        model.payout_stage == icm_stage,
                        model.has_ante.is_(False),
                        model.action == "PUSH_ONLY",
                    )
                row = session.scalar(
                    fallback_statement.order_by(func.abs(model.stack_bb - stack_bb))
                )
                if row is not None:
                    details["used_ante_fallback"] = True

            if row is None:
                return self._fallback("FOLD", details)
            details["strategy_stack_bb"] = row.stack_bb
            return self._range_result(
                action="PUSH",
                hero_combo=hero_combo,
                range_str=row.range_str,
                details=details,
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
        """Return the highest-priority response to a preflop villain action."""
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
                return self._fallback("FOLD", details)

            details["strategy_stack_bb"] = row.stack_bb
            if hero_combo:
                for action, range_str in (
                    ("3BET_PUSH", row.range_3bet_push),
                    ("3BET_RAISE", row.range_3bet_raise),
                    ("CALL", row.range_call),
                ):
                    if range_str and is_combo_in_range(hero_combo, range_str):
                        return self._range_result(
                            action=action,
                            hero_combo=hero_combo,
                            range_str=range_str,
                            details=details,
                        )
                return DecisionResult("FOLD", False, None, None, None, None, False, details)
            else:
                combined_ranges = [r for r in (row.range_3bet_push, row.range_3bet_raise, row.range_call) if r]
                combined_str = ", ".join(combined_ranges) if combined_ranges else None
                return DecisionResult(
                    action="DEFEND",
                    is_in_range=False,
                    range_str=combined_str,
                    range_stats=get_range_stats(combined_str) if combined_str else None,
                    recommended_sizing=None,
                    frequencies=None,
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
            if row is None:
                return self._fallback("CHECK", details)

            frequencies = {
                "check_pct": row.action_check_pct,
                "bet_pct": row.action_bet_pct,
                "raise_pct": row.action_raise_pct,
            }
            action = max(
                (("CHECK", frequencies["check_pct"]), ("BET", frequencies["bet_pct"]), ("RAISE", frequencies["raise_pct"])),
                key=lambda item: item[1],
            )[0]
            return DecisionResult(
                action=action,
                is_in_range=True,
                range_str=None,
                range_stats=None,
                recommended_sizing=row.recommended_sizing,
                frequencies=frequencies,
                is_fallback=False,
                details=details,
            )
        except Exception as exc:
            details["error"] = str(exc)
            return self._fallback("CHECK", details)