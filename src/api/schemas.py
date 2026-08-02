from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.engine.postflop_evaluator import evaluate_postflop
from src.engine.range_matcher import normalize_combo
from src.engine.multiway_resolver import (
    ActionEvent,
    validate_action_sequence,
    POSITION_ORDER,
)
from src.services.session_manager import TableSession


IcmStage = Literal["NORMAL", "BUBBLE", "FINAL_TABLE"]
OpponentStyle = Literal["REG", "TIGHT", "LOOSE"]


class SessionResponse(TableSession):
    hero_position_label: str
    stack_bb: float
    model_config = ConfigDict(from_attributes=True)


class UpdateSessionRequest(BaseModel):
    table_size: Optional[int] = Field(None, ge=2, le=9)
    stack_chips: Optional[int] = Field(None, ge=1)
    stack_bb: Optional[float] = Field(None, ge=0.1)
    blind_level: Optional[int] = Field(None, ge=1)
    icm_stage: Optional[IcmStage] = None
    opponent_style: Optional[OpponentStyle] = None
    has_ante: Optional[bool] = None


class TableSizeRequest(BaseModel):
    table_size: int = Field(ge=2, le=9)


class PreflopDecisionRequest(BaseModel):
    hero_combo: Optional[str] = None
    facing_action: Optional[Literal["OPEN_2.5X", "LIMP", "PUSH"]] = None
    villain_position: Optional[
        Literal["UTG", "UTG+1", "MP", "MP+1", "HJ", "CO", "BTN", "SB", "BB", "BTN/SB"]
    ] = None

    @field_validator("hero_combo")
    @classmethod
    def validate_combo(cls, value: Optional[str]) -> Optional[str]:
        return normalize_combo(value) if value is not None else None

    @field_validator("facing_action", "villain_position", mode="before")
    @classmethod
    def normalize_preflop_values(cls, value: Any) -> Any:
        return value.strip().upper() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_facing_action(self) -> PreflopDecisionRequest:
        if self.facing_action is not None and self.villain_position is None:
            raise ValueError("villain_position is required when facing_action is set")
        return self


class ActionEventSchema(BaseModel):
    position: Literal["UTG", "UTG+1", "MP", "MP+1", "HJ", "CO", "BTN", "SB", "BB", "BTN/SB"]
    action: Literal["LIMP", "OPEN", "CALL", "THREE_BET", "PUSH"]

    @field_validator("position", "action", mode="before")
    @classmethod
    def normalize(cls, value: Any) -> Any:
        return value.strip().upper() if isinstance(value, str) else value


class MultiwayDecisionRequest(BaseModel):
    hero_combo: Optional[str] = None
    action_sequence: list[ActionEventSchema] = Field(min_length=1, max_length=6)

    @field_validator("hero_combo")
    @classmethod
    def validate_combo(cls, value: Optional[str]) -> Optional[str]:
        return normalize_combo(value) if value is not None else None

    @model_validator(mode="after")
    def validate_sequence(self) -> MultiwayDecisionRequest:
        events = [ActionEvent(item.position, item.action) for item in self.action_sequence]
        events_sorted = sorted(
            events,
            key=lambda e: POSITION_ORDER.index(e.position) if e.position in POSITION_ORDER else 99
        )
        validate_action_sequence(events_sorted)
        self.action_sequence = [
            ActionEventSchema(position=e.position, action=e.action) for e in events_sorted
        ]
        return self


class PostflopDecisionRequest(BaseModel):
    hero_cards: str | list[str]
    flop_cards: str | list[str]
    pot_type: Literal["SRP", "3BP"] = "SRP"
    hero_role: Literal["PFR", "PFC", "CALLER"] = "PFR"
    hero_position: Literal["IP", "OOP"] = "IP"

    @field_validator("pot_type", "hero_role", "hero_position", mode="before")
    @classmethod
    def normalize_postflop_values(cls, value: Any) -> Any:
        return value.strip().upper() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_cards(self) -> PostflopDecisionRequest:
        evaluate_postflop(self.hero_cards, self.flop_cards)
        return self


class ActionRanges(BaseModel):
    """Stable four-colour payload consumed by the 13x13 matrix."""

    push: dict[str, float] = Field(default_factory=dict)
    raise_: dict[str, float] = Field(default_factory=dict, alias="raise")
    isolate: dict[str, float] = Field(default_factory=dict)
    call: dict[str, float] = Field(default_factory=dict)
    model_config = ConfigDict(populate_by_name=True)


class DecisionResponse(BaseModel):
    action: str
    is_in_range: bool
    range_str: Optional[str]
    range_stats: Optional[dict[str, Any]]
    recommended_sizing: Optional[str]
    frequencies: Optional[dict[str, float]]
    equity_pct: Optional[float] = None
    is_fallback: bool = False
    details: dict[str, Any] = Field(default_factory=dict)
    action_ranges: ActionRanges = Field(default_factory=ActionRanges)
    model_config = ConfigDict(from_attributes=True)
