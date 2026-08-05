"""Generate and UPSERT a deterministic tournament strategy data set."""
from __future__ import annotations
import logging
from collections.abc import Iterable, Sequence
from typing import Any
from sqlalchemy import Engine
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import scoped_session, sessionmaker
from src.utils.range_validator import validate_range_str_raise
from src.engine.position_utils import POSITIONS_BY_SIZE, position_risk
from .base import Base, SessionLocal, engine
from .init_db import FLOP_TEXTURES, HAND_BUCKETS, POSITION_LABELS
from .models import (
    BlindStructure,
    FacingActionRange,
    FlopTexture,
    HandBucket,
    IcmPushFold,
    LimpCallRange,
    LimpRange,
    NashPushFold,
    OpenRange,
    PositionLabel,
    PostflopStrategy,
)

LOGGER = logging.getLogger(__name__)
STACKS = (3, 5, 8, 10, 12, 15)
OPEN_STACKS = (15, 20, 30, 40, 50, 80, 100)
STYLES = ("TIGHT", "REG", "LOOSE")
ICM_STAGES = ("BUBBLE", "FINAL_TABLE", "PAY_JUMP")

# Откалиброванные GTO MTT диапазоны открытий (First-In Open Ranges)
GTO_OPEN_RANGES_BY_STACK = {
    # UTG (~8.3% - 14.5%)
    ("UTG", 15): "88+, ATs+, KQs, AJo+, KQo",
    ("UTG", 20): "77+, A9s+, KTs+, QTs+, AJo+, KQo",
    ("UTG", 30): "66+, A8s+, KTs+, QTs+, JTs, ATo+, KQo",
    ("UTG", 40): "55+, A8s+, KTs+, QTs+, JTs, ATo+, KQo",
    ("UTG", 50): "55+, A5s+, KTs+, QTs+, JTs, T9s, ATo+, KQo",
    ("UTG", 80): "44+, A4s+, K9s+, QTs+, JTs, T9s, ATo+, KJo+",
    ("UTG", 100): "33+, A2s+, K9s+, QTs+, JTs, T9s, AJo+, KJo+",

    # UTG+1 (~10.3% - 17.0%)
    ("UTG+1", 15): "77+, A9s+, KTs+, QTs+, AJo+, KQo",
    ("UTG+1", 20): "66+, A8s+, KTs+, QTs+, JTs, ATo+, KQo",
    ("UTG+1", 30): "55+, A5s+, K9s+, Q9s+, JTs, T9s, ATo+, KQo",
    ("UTG+1", 40): "55+, A4s+, K9s+, Q9s+, JTs, T9s, ATo+, KJo+",
    ("UTG+1", 50): "44+, A3s+, K9s+, Q9s+, JTs, T9s, ATo+, KJo+",
    ("UTG+1", 80): "33+, A2s+, K8s+, Q9s+, J9s+, T9s, 98s, AJo+, KJo+",
    ("UTG+1", 100): "33+, A2s+, K8s+, Q9s+, J9s+, T9s, 98s, ATo+, KJo+",

    # MP (~12.2% - 20.5%)
    ("MP", 15): "66+, A8s+, KTs+, QTs+, JTs, ATo+, KQo",
    ("MP", 20): "55+, A5s+, K9s+, Q9s+, JTs, T9s, ATo+, KQo",
    ("MP", 30): "44+, A3s+, K9s+, Q9s+, JTs, T9s, 98s, ATo+, KJo+",
    ("MP", 40): "44+, A2s+, K9s+, Q9s+, JTs, T9s, 98s, ATo+, KJo+",
    ("MP", 50): "33+, A2s+, K8s+, Q9s+, J9s+, T9s, 98s, ATo+, KJo+",
    ("MP", 80): "22+, A2s+, K7s+, Q9s+, J9s+, T9s, 98s, 87s, ATo+, KJo+",
    ("MP", 100): "22+, A2s+, K6s+, Q9s+, J9s+, T9s, 98s, 87s, ATo+, KJo+, QJo",

    # MP+1 (~13.9% - 25.0%)
    ("MP+1", 15): "55+, A7s+, K9s+, Q9s+, JTs, T9s, ATo+, KQo",
    ("MP+1", 20): "44+, A4s+, K9s+, Q9s+, JTs, T9s, ATo+, KJo+",
    ("MP+1", 30): "33+, A3s+, K9s+, Q9s+, JTs, T9s, 98s, ATo+, KJo+",
    ("MP+1", 40): "33+, A2s+, K8s+, Q9s+, J9s+, T8s+, 98s, A9o+, KTo+, QJo",
    ("MP+1", 50): "33+, A2s+, K7s+, Q9s+, J9s+, T8s+, 98s, 87s, A9o+, KTo+, QJo",
    ("MP+1", 80): "22+, A2s+, K6s+, Q9s+, J9s+, T8s+, 98s, 87s, A9o+, KTo+, QJo",
    ("MP+1", 100): "22+, A2s+, K5s+, Q8s+, J8s+, T8s+, 98s, 87s, 76s, A9o+, KTo+, QJo",

    # HJ (~15.4% - 28.0%)
    ("HJ", 15): "55+, A5s+, K9s+, Q9s+, JTs, T9s, ATo+, KJo+",
    ("HJ", 20): "44+, A3s+, K9s+, Q9s+, JTs, T9s, 98s, A9o+, KTo+, QJo",
    ("HJ", 30): "33+, A2s+, K8s+, Q9s+, J9s+, T8s+, 98s, A9o+, KTo+, QJo",
    ("HJ", 40): "33+, A2s+, K7s+, Q9s+, J9s+, T8s+, 98s, 87s, A9o+, KTo+, QJo",
    ("HJ", 50): "22+, A2s+, K6s+, Q8s+, J8s+, T8s+, 97s+, 87s, A8o+, K9o+, QJo",
    ("HJ", 80): "22+, A2s+, K5s+, Q8s+, J8s+, T8s+, 97s+, 87s, 76s, A8o+, K9o+, QJo",
    ("HJ", 100): "22+, A2s+, K4s+, Q7s+, J8s+, T8s+, 97s+, 87s, 76s, A7o+, K9o+, QTo+, JTo",

    # CO (~21.0% - 33.2%)
    ("CO", 15): "44+, A2s+, K8s+, Q9s+, J9s+, T9s, A8o+, KTo+, QJo",
    ("CO", 20): "33+, A2s+, K6s+, Q8s+, J8s+, T8s+, 98s, A7o+, K9o+, QJo",
    ("CO", 30): "22+, A2s+, K5s+, Q8s+, J8s+, T8s+, 97s+, 87s, 76s, A8o+, K9o+, QJo",
    ("CO", 40): "22+, A2s+, K4s+, Q7s+, J8s+, T8s+, 97s+, 87s, 76s, A7o+, K9o+, QTo+, JTo",
    ("CO", 50): "22+, A2s+, K3s+, Q6s+, J7s+, T7s+, 97s+, 87s, 76s, 65s, A5o+, K9o+, QTo+, JTo",
    ("CO", 80): "22+, A2s+, K2s+, Q5s+, J7s+, T7s+, 97s+, 87s, 76s, 65s, A4o+, K8o+, Q9o+, J9o+",
    ("CO", 100): "22+, A2s+, K2s+, Q4s+, J6s+, T7s+, 96s+, 86s+, 75s+, 65s, A3o+, K8o+, Q9o+, J9o+, T9o",

    # BTN (~35.4% - 48.0%)
    ("BTN", 15): "22+, A2s+, K4s+, Q7s+, J8s+, T8s+, 98s, A2o+, K8o+, Q9o+, J9o+",
    ("BTN", 20): "22+, A2s+, K2s+, Q6s+, J7s+, T7s+, 97s+, 87s, A2o+, K7o+, Q9o+, J9o+",
    ("BTN", 30): "22+, A2s+, K2s+, Q4s+, J6s+, T7s+, 97s+, 86s+, 75s+, A2o+, K6o+, Q8o+, J8o+, T8o",
    ("BTN", 40): "22+, A2s+, K2s+, Q3s+, J5s+, T6s+, 96s+, 86s+, 75s+, 65s, A2o+, K5o+, Q8o+, J8o+, T8o",
    ("BTN", 50): "22+, A2s+, K2s+, Q2s+, J5s+, T6s+, 96s+, 86s+, 75s+, 65s, A2o+, K4o+, Q8o+, J8o+, T8o",
    ("BTN", 80): "22+, A2s+, K2s+, Q2s+, J4s+, T5s+, 95s+, 85s+, 75s+, 64s+, 54s, A2o+, K3o+, Q7o+, J7o+, T8o+",
    ("BTN", 100): "22+, A2s+, K2s+, Q2s+, J3s+, T5s+, 95s+, 84s+, 74s+, 64s+, 54s, A2o+, K2o+, Q7o+, J7o+, T8o+, 97o+",

    # SB / BTN/SB (~36.7% - 53.0%)
    ("SB", 15): "22+, A2s+, K3s+, Q7s+, J8s+, T8s+, 98s, A2o+, K7o+, Q9o+, J9o+",
    ("SB", 20): "22+, A2s+, K2s+, Q5s+, J6s+, T7s+, 97s+, 86s+, 75s+, A2o+, K5o+, Q8o+, J8o+, T8o",
    ("SB", 30): "22+, A2s+, K2s+, Q4s+, J6s+, T7s+, 97s+, 86s+, 75s+, A2o+, K5o+, Q8o+, J8o+, T8o",
    ("SB", 40): "22+, A2s+, K2s+, Q3s+, J5s+, T6s+, 96s+, 85s+, 75s+, 64s+, 54s, A2o+, K3o+, Q7o+, J7o+, T8o+",
    ("SB", 50): "22+, A2s+, K2s+, Q2s+, J4s+, T5s+, 95s+, 84s+, 74s+, 64s+, 54s, A2o+, K2o+, Q6o+, J7o+, T7o+, 97o+",
    ("SB", 80): "22+, A2s+, K2s+, Q2s+, J3s+, T4s+, 94s+, 84s+, 74s+, 63s+, 53s+, 43s, A2o+, K2o+, Q5o+, J6o+, T7o+, 96o+",
    ("SB", 100): "22+, A2s+, K2s+, Q2s+, J3s+, T4s+, 94s+, 84s+, 73s+, 63s+, 53s+, 43s, A2o+, K2o+, Q4o+, J6o+, T7o+, 96o+, 86o+",
}

# Дублируем значения SB для позиции BTN/SB (Heads-Up)
for stack in OPEN_STACKS:
    GTO_OPEN_RANGES_BY_STACK[("BTN/SB", stack)] = GTO_OPEN_RANGES_BY_STACK[("SB", stack)]

PUSH_RANGES = (
    "22+, A2s+, K2s+, Q2s+, J2s+, T2s+, 92s+, 82s+, 72s+, 62s+, 52s+, 42s+, 32s, A2o+, K2o+, Q2o+, J2o+, T2o+, 92o+, 82o+, 72o+, 62o+, 52o+, 42o+, 32o",
    "22+, A2s+, K2s+, Q2s+, J4s+, T6s+, 96s+, 86s+, 75s+, A2o+, K4o+, Q7o+, J8o+, T8o+",
    "22+, A2s+, K4s+, Q7s+, J8s+, T8s+, 98s, A5o+, K9o+, QTo+, JTo",
    "22+, A2s+, K7s+, Q9s+, J9s+, T9s, A8o+, KTo+, QJo",
    "33+, A5s+, K9s+, QTs+, JTs, ATo+, KQo",
    "55+, A9s+, KJs+, QJs, AJo+, KQo",
)


def _position_pressure(table_size: int, position: str) -> int:
    return round(position_risk(table_size, position) * 4)


def _push_range(table_size: int, position: str, stack_bb: int, adjustment: int = 0) -> str:
    stack_tightness = STACKS.index(stack_bb)
    tier = max(0, min(5, stack_tightness - _position_pressure(table_size, position) + adjustment))
    return PUSH_RANGES[tier]


def generate_reference_rows() -> dict[type[Any], list[dict[str, Any]]]:
    positions = [
        {"table_size": size, "seat_index": seat, "label": label}
        for size, labels in POSITION_LABELS.items()
        for seat, label in enumerate(labels)
    ]
    return {
        PositionLabel: positions,
        FlopTexture: list(FLOP_TEXTURES),
        HandBucket: list(HAND_BUCKETS),
    }


def generate_open_ranges() -> list[dict[str, Any]]:
    rows = []
    positions = ("UTG", "UTG+1", "MP", "MP+1", "HJ", "CO", "BTN", "SB", "BTN/SB")
    for position in positions:
        for stack_bb in OPEN_STACKS:
            base_range = GTO_OPEN_RANGES_BY_STACK.get(
                (position, stack_bb),
                GTO_OPEN_RANGES_BY_STACK.get((position, 30), "22+, A2s+, K9s+, A8o+, KTo+"),
            )
            for style in STYLES:
                rows.append({
                    "position": position,
                    "stack_bb": stack_bb,
                    "style": style,
                    "range_str": base_range,
                })
    return rows


def _generate_limp_rows(*, call: bool) -> list[dict[str, Any]]:
    positions = ("UTG", "UTG+1", "MP", "MP+1", "HJ", "CO", "BTN", "SB", "BTN/SB")
    if call:
        positions = (*positions, "BB")
    rows: list[dict[str, Any]] = []
    for position in positions:
        for stack_bb in OPEN_STACKS:
            for style in STYLES:
                range_str = (
                    "99-22, A2s+, K8s+, Q9s+, J9s+, T9s, 98s, 87s"
                    if call else
                    "77-22, A2s+, K8s+, Q9s+, J9s+, T9s, 98s, 87s, 76s"
                )
                if style == "TIGHT":
                    range_str = "66-22, A2s+, KTs+, QTs+, JTs, T9s, 98s"
                elif style == "LOOSE":
                    range_str = f"{range_str}, 65s, 54s" + (", ATo, KQo" if call else "")
                rows.append({"position": position, "stack_bb": stack_bb, "style": style,
                             "range_str": range_str})
    return rows


def generate_limp_ranges() -> list[dict[str, Any]]:
    return _generate_limp_rows(call=False)


def generate_limp_call_ranges() -> list[dict[str, Any]]:
    return _generate_limp_rows(call=True)


def generate_nash_ranges() -> list[dict[str, Any]]:
    return [
        {
            "table_size": size,
            "position": position,
            "stack_bb": stack,
            "has_ante": has_ante,
            "action": "PUSH_ONLY",
            "range_str": _push_range(size, position, stack, -1 if has_ante else 0),
        }
        for size, positions in POSITIONS_BY_SIZE.items()
        for position in positions[:-1]
        for stack in STACKS
        for has_ante in (False, True)
    ]


def generate_icm_ranges() -> list[dict[str, Any]]:
    stage_adjustment = {"BUBBLE": 1, "FINAL_TABLE": 1, "PAY_JUMP": 2}
    return [
        {
            "table_size": size,
            "position": position,
            "stack_bb": stack,
            "payout_stage": stage,
            "has_ante": has_ante,
            "action": "PUSH_ONLY",
            "range_str": _push_range(
                size, position, stack, stage_adjustment[stage] - (1 if has_ante else 0)
            ),
        }
        for size, positions in POSITIONS_BY_SIZE.items()
        for position in positions[:-1]
        for stack in STACKS
        for stage in ICM_STAGES
        for has_ante in (False, True)
    ]


def generate_facing_action_ranges() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    all_positions = ("UTG", "UTG+1", "MP", "MP+1", "HJ", "CO", "BTN", "SB", "BB")
    for villain_index, villain in enumerate(all_positions[:-1]):
        for hero in all_positions[villain_index + 1 :]:
            for stack in (15, 20, 30, 50, 80, 100):
                for style in STYLES:
                    for action in ("OPEN_2.5X", "LIMP", "PUSH"):
                        is_late_villain = villain in ("CO", "BTN", "SB")
                        is_bb_hero = hero == "BB"
                        is_short = stack <= 20
                        is_medium = 20 < stack <= 50
                        is_loose = style == "LOOSE"
                        is_tight = style == "TIGHT"
                        if action == "PUSH":
                            push_range = None
                            raise_range = None
                            if is_bb_hero and is_late_villain:
                                call_range = (
                                    "22+, A2s+, K5s+, Q8s+, J8s+, T8s+, A2o+, K8o+, QTo+, JTo"
                                    if is_loose
                                    else "55+, A5s+, K9s+, QTs+, A8o+, KQo"
                                    if not is_tight
                                    else "77+, ATs+, KQs, AJo+"
                                )
                            elif is_late_villain:
                                call_range = (
                                    "66+, A8s+, KQs, AJo+"
                                    if is_loose
                                    else "88+, ATs+, AQo+"
                                    if not is_tight
                                    else "TT+, AQs+, AKo"
                                )
                            else:
                                call_range = (
                                    "88+, ATs+, AQo+"
                                    if is_loose
                                    else "TT+, AQs+, AKo"
                                    if not is_tight
                                    else "JJ+, AKs, AKo"
                                )
                        elif action == "LIMP":
                            if is_short:
                                push_range = (
                                    "55+, A8s+, KTs+, AJo+"
                                    if is_late_villain
                                    else "88+, ATs+, AQo+"
                                )
                                raise_range = None
                                call_range = (
                                    "22+, A2s+, K5s+, Q8s+, J8s+, T8s+, A2o+, K7o+"
                                    if is_bb_hero
                                    else "44-22, A2s+, K9s+, QTs+, JTs"
                                )
                            else:
                                push_range = None
                                raise_range = (
                                    "22+, A2s+, K8s+, Q9s+, J9s+, A7o+, K9o+"
                                    if (is_late_villain or is_bb_hero)
                                    else "77+, ATs+, KQs, AJo+"
                                )
                                call_range = (
                                    "66-22, A2s+, K8s+, Q9s+, J9s+, T8s+, 98s, 87s"
                                    if not is_bb_hero
                                    else "55-22, A2s+, K2s+, Q2s+, J5s+, T6s+, 96s+, 86s+, 75s+"
                                )
                        else:  # OPEN_2.5X
                            if is_short:
                                push_range = (
                                    "TT-77, AJs+, AQo, AKo"
                                    if is_late_villain
                                    else "JJ-TT, AKs, AKo"
                                )
                                raise_range = (
                                    "QQ+, AKs"
                                    if not is_late_villain
                                    else "JJ+, AKs, AKo"
                                )
                                call_range = (
                                    "22+, A2s+, K2s+, Q5s+, J7s+, T7s+, 97s+, 86s+, A2o+, K7o+, Q9o+"
                                    if is_bb_hero
                                    else "99-55, ATs+, KQs, QJs, JTs"
                                )
                            elif is_medium:
                                push_range = (
                                    "TT-99, AJs, AQo" if is_late_villain else None
                                )
                                raise_range = (
                                    "88+, AJs+, KQs, AQo+"
                                    if is_late_villain
                                    else "JJ+, AQs+, AKo"
                                )
                                call_range = (
                                    "22+, A2s+, K2s+, Q4s+, J6s+, T7s+, 97s+, 86s+, 75s+, A2o+, K5o+, Q8o+, J8o+, T8o"
                                    if is_bb_hero
                                    else "TT-22, A8s+, KTs+, QTs+, JTs, T9s, 98s, ATo+"
                                )
                            else:  # Deep stack (80-100 BB)
                                push_range = None
                                raise_range = (
                                    "77+, A9s+, KTs+, QTs+, JTs, T9s, AJo+, KQo"
                                    if is_late_villain
                                    else "99+, AJs+, KQs, AQo+"
                                )
                                call_range = (
                                    "22+, A2s+, K2s+, Q2s+, J4s+, T6s+, 95s+, 85s+, 74s+, 64s+, 54s, A2o+, K3o+, Q7o+, J7o+, T7o+, 97o+"
                                    if is_bb_hero
                                    else "99-22, A2s+, K9s+, Q9s+, J9s+, T8s+, 98s, 87s, 76s, 65s"
                                )
                        rows.append(
                            {
                                "hero_position": hero,
                                "villain_position": villain,
                                "villain_action": action,
                                "stack_bb": stack,
                                "opponent_style": style,
                                "range_3bet_push": push_range,
                                "range_3bet_raise": raise_range,
                                "range_call": call_range,
                            }
                        )
    return rows


def generate_blind_structures() -> list[dict[str, Any]]:
    structures = {
        "TURBO": (
            (25, 50), (50, 100), (75, 150), (100, 200), (150, 300), (200, 400),
            (300, 600), (400, 800), (600, 1200), (800, 1600), (1000, 2000),
            (1500, 3000), (2000, 4000), (3000, 6000), (5000, 10000), (8000, 16000),
            (10000, 20000), (15000, 30000), (20000, 40000), (25000, 50000),
            (35000, 70000), (50000, 100000), (75000, 150000), (100000, 200000),
            (150000, 300000), (200000, 400000), (300000, 600000), (500000, 1000000),
            (750000, 1500000), (1000000, 2000000)
        ),
        "REGULAR": (
            (25, 50), (40, 80), (50, 100), (75, 150), (100, 200), (150, 300),
            (200, 400), (250, 500), (300, 600), (400, 800), (500, 1000),
            (750, 1500), (1000, 2000), (1500, 3000), (2000, 4000), (3000, 6000),
            (4000, 8000), (5000, 10000), (7500, 15000), (10000, 20000),
            (15000, 30000), (20000, 40000), (3000, 60000), (50000, 100000),
            (75000, 150000), (100000, 200000), (150000, 300000), (250000, 500000),
            (500000, 1000000), (1000000, 2000000)
        ),
        "DEEP": (
            (25, 50), (30, 60), (40, 80), (50, 100), (60, 120), (75, 150),
            (100, 200), (125, 250), (150, 300), (200, 400), (250, 500),
            (300, 600), (400, 800), (500, 1000), (750, 1500), (1000, 2000),
            (1500, 3000), (2000, 4000), (2500, 5000), (3000, 6000),
            (4000, 8000), (5000, 10000), (7500, 15000), (10000, 20000),
            (15000, 30000), (20000, 40000), (30000, 60000), (50000, 100000),
            (100000, 200000), (500000, 1000000)
        ),
    }
    return [
        {
            "structure_id": structure_id,
            "level": level,
            "sb_chips": sb,
            "bb_chips": bb,
            "ante_chips": 0 if level <= 2 else max(1, bb // 8),
        }
        for structure_id, levels in structures.items()
        for level, (sb, bb) in enumerate(levels, start=1)
    ]


def _postflop_frequencies(
    pot_type: str, hero_role: str, hero_position: str, texture: str, bucket: str
) -> tuple[int, int, int, str]:
    if hero_role == "PFR":
        bet = 68 if texture == "DRY_RAINBOW" else 42
        if hero_position == "OOP":
            bet -= 12
        if bucket == "MONSTER":
            return 20, 70, 10, "BET_67%_POT"
        if bucket in ("TPTK", "TPGK"):
            bet += 15
        elif bucket in ("WEAK_PAIR", "GUTSHOT"):
            bet -= 20
        elif bucket == "AIR":
            bet -= 10
        bet = max(10, min(85, bet - (8 if pot_type == "3BP" else 0)))
        return 100 - bet, bet, 0, "BET_33%_POT" if texture == "DRY_RAINBOW" else "BET_67%_POT"
    raise_pct = 18 if bucket in ("MONSTER", "NUT_DRAW") else 5 if bucket == "TPTK" else 0
    bet = 18 if hero_position == "IP" and bucket in ("AIR", "NUT_DRAW") else 0
    return 100 - raise_pct - bet, bet, raise_pct, "RAISE_3X" if raise_pct else "CHECK"


def generate_postflop_strategies() -> list[dict[str, Any]]:
    rows = []
    for pot_type in ("SRP", "3BP"):
        for role in ("PFR", "PFC", "CALLER"):
            for position in ("IP", "OOP"):
                for texture in (item["texture_id"] for item in FLOP_TEXTURES):
                    for bucket in (item["bucket_id"] for item in HAND_BUCKETS):
                        for depth in ("SHORT", "MEDIUM", "DEEP"):
                            check, bet, raise_pct, sizing = _postflop_frequencies(
                                pot_type, role, position, texture, bucket
                            )
                            rows.append({
                                "pot_type": pot_type,
                                "hero_role": role,
                                "hero_position": position,
                                "texture_id": texture,
                                "bucket_id": bucket,
                                "stack_depth": depth,
                                "action_check_pct": check,
                                "action_bet_pct": bet,
                                "action_raise_pct": raise_pct,
                                "recommended_sizing": sizing,
                            })
    return rows


def generate_tournament_data() -> dict[type[Any], list[dict[str, Any]]]:
    data = generate_reference_rows()
    data.update({
        OpenRange: generate_open_ranges(),
        LimpRange: generate_limp_ranges(),
        LimpCallRange: generate_limp_call_ranges(),
        NashPushFold: generate_nash_ranges(),
        IcmPushFold: generate_icm_ranges(),
        FacingActionRange: generate_facing_action_ranges(),
        BlindStructure: generate_blind_structures(),
        PostflopStrategy: generate_postflop_strategies(),
    })
    return data


def _validate_rows(rows: Iterable[dict[str, Any]]) -> None:
    for row in rows:
        for field_name, value in row.items():
            if field_name.startswith("range_") and value is not None:
                validate_range_str_raise(value)
        frequency_fields = ("action_check_pct", "action_bet_pct", "action_raise_pct")
        if all(field in row for field in frequency_fields):
            if sum(row[field] for field in frequency_fields) != 100:
                raise ValueError(f"Postflop frequencies do not total 100: {row}")


def _validate_strategy_coverage(data: dict[type[Any], list[dict[str, Any]]]) -> None:
    """Fail before touching SQLite when a generated strategy dimension is missing."""
    def require_exact(model: type[Any], expected: set[tuple[Any, ...]]) -> None:
        primary_key = tuple(column.name for column in model.__table__.primary_key.columns)
        actual = {tuple(row[field] for field in primary_key) for row in data[model]}
        if len(actual) != len(data[model]):
            raise ValueError(f"Duplicate primary keys generated for {model.__name__}")
        missing = expected - actual
        unexpected = actual - expected
        if missing or unexpected:
            raise ValueError(
                f"Incomplete {model.__name__} coverage: "
                f"missing={len(missing)}, unexpected={len(unexpected)}"
            )
    open_positions = ("UTG", "UTG+1", "MP", "MP+1", "HJ", "CO", "BTN", "SB", "BTN/SB")
    require_exact(OpenRange, {
        (position, stack, style)
        for position in open_positions for stack in OPEN_STACKS for style in STYLES
    })
    require_exact(LimpRange, {
        (position, stack, style) for position in open_positions
        for stack in OPEN_STACKS for style in STYLES
    })
    require_exact(LimpCallRange, {
        (position, stack, style) for position in (*open_positions, "BB")
        for stack in OPEN_STACKS for style in STYLES
    })
    require_exact(NashPushFold, {
        (size, position, stack, ante, "PUSH_ONLY")
        for size, positions in POSITIONS_BY_SIZE.items()
        for position in positions[:-1]
        for stack in STACKS
        for ante in (False, True)
    })
    require_exact(IcmPushFold, {
        (size, position, stack, stage, ante, "PUSH_ONLY")
        for size, positions in POSITIONS_BY_SIZE.items()
        for position in positions[:-1]
        for stack in STACKS
        for stage in ICM_STAGES
        for ante in (False, True)
    })
    positions = ("UTG", "UTG+1", "MP", "MP+1", "HJ", "CO", "BTN", "SB", "BB")
    require_exact(FacingActionRange, {
        (hero, villain, action, stack, style)
        for villain_index, villain in enumerate(positions[:-1])
        for hero in positions[villain_index + 1 :]
        for stack in (15, 20, 30, 50, 80, 100)
        for style in STYLES
        for action in ("OPEN_2.5X", "LIMP", "PUSH")
    })
    for row in data[FacingActionRange]:
        if not any(row[field] for field in ("range_3bet_push", "range_3bet_raise", "range_call")):
            raise ValueError(f"FacingActionRange has no playable combinations: {row}")


def _chunks(rows: Sequence[dict[str, Any]], size: int = 250) -> Iterable[Sequence[dict[str, Any]]]:
    for start in range(0, len(rows), size):
        yield rows[start : start + size]


def _upsert_rows(session: Any, model: type[Any], rows: list[dict[str, Any]]) -> None:
    table = model.__table__
    for chunk in _chunks(rows):
        statement = insert(table).values(chunk)
        updates = {
            column.name: statement.excluded[column.name]
            for column in table.columns
            if not column.primary_key
        }
        session.execute(statement.on_conflict_do_update(
            index_elements=list(table.primary_key.columns), set_=updates
        ))


def seed_tournament_data(
    session_factory: scoped_session[sessionmaker[Any]] = SessionLocal,
    bind: Engine = engine,
) -> dict[str, int]:
    data = generate_tournament_data()
    _validate_strategy_coverage(data)
    for rows in data.values():
        _validate_rows(rows)
    Base.metadata.create_all(bind=bind)
    counts: dict[str, int] = {}
    with session_factory() as session:
        with session.begin():
            for model, rows in data.items():
                _upsert_rows(session, model, rows)
                counts[model.__tablename__] = len(rows)
    return counts


seed_fixtures = seed_tournament_data

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    seeded = seed_tournament_data()
    for table_name, count in seeded.items():
        LOGGER.info("UPSERT %s: %d rows", table_name, count)
    print(f"Tournament data UPSERT completed: {sum(seeded.values())} rows in poker.db")