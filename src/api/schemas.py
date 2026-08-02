from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
from src.services.session_manager import TableSession

class SessionResponse(TableSession):
    hero_position_label: str
    stack_bb: float
    model_config = ConfigDict(from_attributes=True)

class UpdateSessionRequest(BaseModel):
    table_size: Optional[int] = Field(None, ge=2, le=9)
    stack_chips: Optional[int] = Field(None, ge=1)
    blind_level: Optional[int] = Field(None, ge=1)
    icm_stage: Optional[str] = None
    opponent_style: Optional[str] = None
    has_ante: Optional[bool] = None

class TableSizeRequest(BaseModel): table_size: int = Field(ge=2, le=9)

class PreflopDecisionRequest(BaseModel):
    hero_combo: Optional[str] = None  # Сделали необязательным
    facing_action: Optional[str] = None
    villain_position: Optional[str] = None

class PostflopDecisionRequest(BaseModel):
    hero_cards: str | list[str]
    flop_cards: str | list[str]
    pot_type: str = "SRP"; hero_role: str = "PFR"; hero_position: str = "IP"