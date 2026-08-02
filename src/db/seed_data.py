"""Generate and UPSERT a deterministic tournament strategy data set."""

from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence
from typing import Any

from sqlalchemy import Engine
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import scoped_session, sessionmaker

from src.utils.range_validator import validate_range_str_raise

from .base import Base, SessionLocal, engine
from .init_db import FLOP_TEXTURES, HAND_BUCKETS, POSITION_LABELS
from .models import (
    BlindStructure,
    FacingActionRange,
    FlopTexture,
    HandBucket,
    IcmPushFold,
    NashPushFold,
    OpenRange,
    PositionLabel,
    PostflopStrategy,
)


LOGGER = logging.getLogger(__name__)
STACKS = (3, 5, 8, 10, 12, 15)
STYLES = ("TIGHT", "REG", "LOOSE")
ICM_STAGES = ("BUBBLE", "FINAL_TABLE", "PAY_JUMP")

# Ordered from early to late. BB is excluded because it cannot open first-in.
POSITIONS_BY_SIZE: dict[int, tuple[str, ...]] = {
    2: ("BTN/SB", "BB"),
    6: ("UTG", "HJ", "CO", "BTN", "SB", "BB"),
    8: ("UTG", "MP", "MP+1", "HJ", "CO", "BTN", "SB", "BB"),
    9: ("UTG", "UTG+1", "MP", "MP+1", "HJ", "CO", "BTN", "SB", "BB"),
}

OPEN_RANGES = {
    "UTG": "66+, ATs+, KQs, AQo+",
    "UTG+1": "55+, A9s+, KJs+, QJs, AJo+, KQo",
    "MP": "44+, A7s+, KTs+, QTs+, JTs, ATo+, KQo",
    "MP+1": "33+, A5s+, K9s+, Q9s+, JTs, T9s, ATo+, KJo+",
    "HJ": "22+, A2s+, K8s+, Q9s+, J9s+, T9s, A9o+, KTo+, QJo",
    "CO": "22+, A2s+, K5s+, Q8s+, J8s+, T8s+, 98s, A7o+, K9o+, QTo+, JTo",
    "BTN": "22+, A2s+, K2s+, Q5s+, J7s+, T7s+, 97s+, 87s, A2o+, K7o+, Q9o+, J9o+, T9o",
    "SB": "22+, A2s+, K2s+, Q4s+, J6s+, T7s+, 97s+, 86s+, A2o+, K7o+, Q9o+, J9o+",
    "BTN/SB": "22+, A2s+, K2s+, Q2s+, J4s+, T6s+, 96s+, 86s+, 75s+, A2o+, K2o+, Q6o+, J7o+, T8o+",
}

PUSH_RANGES = (
    "22+, A2s+, K2s+, Q2s+, J2s+, T2s+, 92s+, 82s+, 72s+, 62s+, 52s+, 42s+, 32s, A2o+, K2o+, Q2o+, J2o+, T2o+, 92o+, 82o+, 72o+, 62o+, 52o+, 42o+, 32o",
    "22+, A2s+, K2s+, Q2s+, J4s+, T6s+, 96s+, 86s+, 75s+, A2o+, K4o+, Q7o+, J8o+, T8o+",
    "22+, A2s+, K4s+, Q7s+, J8s+, T8s+, 98s, A5o+, K9o+, QTo+, JTo",
    "22+, A2s+, K7s+, Q9s+, J9s+, T9s, A8o+, KTo+, QJo",
    "33+, A5s+, K9s+, QTs+, JTs, ATo+, KQo",
    "55+, A9s+, KJs+, QJs, AJo+, KQo",
)


def _position_pressure(table_size: int, position: str) -> int:
    """Return a late-position bonus on a six-step range scale."""
    positions = POSITIONS_BY_SIZE[table_size]
    index = positions.index(position)
    return round(index * 4 / max(1, len(positions) - 1))


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
    for position, base_range in OPEN_RANGES.items():
        for style in STYLES:
            range_str = base_range
            if style == "TIGHT":
                range_str = PUSH_RANGES[5 if position in ("UTG", "UTG+1", "MP") else 4]
            elif style == "LOOSE" and position not in ("UTG", "UTG+1"):
                range_str = PUSH_RANGES[2 if position in ("HJ", "CO") else 1]
            rows.append({"position": position, "style": style, "range_str": range_str})
    return rows


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
    positions = POSITIONS_BY_SIZE[9][:-1]
    for villain_index, villain in enumerate(positions[:-1]):
        for hero in positions[villain_index + 1 :]:
            for stack in (15, 20, 30, 50, 80):
                for style in STYLES:
                    for action in ("OPEN_2.5X", "LIMP", "PUSH"):
                        aggressive = style == "LOOSE"
                        short = stack <= 20
                        if action == "PUSH":
                            push_range = None
                            raise_range = None
                            call_range = "77+, AJs+, AQo+" if aggressive else "TT+, AQs+, AKo"
                        elif action == "LIMP":
                            push_range = "77+, AJs+, AQo+" if short else None
                            raise_range = None if short else "88+, ATs+, KQs, AJo+"
                            call_range = "22+, A2s+, K9s+, QTs+, JTs, T9s, ATo+, KQo"
                        else:
                            push_range = (
                                "88+, AQs+, AKo" if short and aggressive else
                                "TT+, AKs, AKo" if short else None
                            )
                            raise_range = (
                                "99+, AJs+, KQs, AQo+" if aggressive else "JJ+, AQs+, AKo"
                            ) if not short else None
                            call_range = (
                                "22+, A2s+, KTs+, QTs+, JTs, T9s, AJo+, KQo"
                                if aggressive else "66+, ATs+, KJs+, QJs, AJo+, KQo"
                            )
                        rows.append({
                            "hero_position": hero,
                            "villain_position": villain,
                            "villain_action": action,
                            "stack_bb": stack,
                            "opponent_style": style,
                            "range_3bet_push": push_range,
                            "range_3bet_raise": raise_range,
                            "range_call": call_range,
                        })
    return rows


def generate_blind_structures() -> list[dict[str, Any]]:
    structures = {
        "TURBO": ((25, 50), (50, 100), (75, 150), (100, 200), (150, 300), (200, 400), (300, 600), (400, 800), (600, 1200), (800, 1600), (1000, 2000), (1500, 3000), (2000, 4000), (3000, 6000), (5000, 10000)),
        "REGULAR": ((25, 50), (40, 80), (50, 100), (75, 150), (100, 200), (150, 300), (200, 400), (250, 500), (300, 600), (400, 800), (500, 1000), (750, 1500), (1000, 2000), (1500, 3000), (2000, 4000)),
        "DEEP": ((25, 50), (30, 60), (40, 80), (50, 100), (60, 120), (75, 150), (100, 200), (125, 250), (150, 300), (200, 400), (250, 500), (300, 600), (400, 800), (500, 1000), (750, 1500)),
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
        # PFC is the public API name; CALLER remains populated for old clients.
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
    """Build every row without random state so repeated seeds are reproducible."""
    data = generate_reference_rows()
    data.update({
        OpenRange: generate_open_ranges(),
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
    """Create the schema and atomically UPSERT the generated data set."""
    data = generate_tournament_data()
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


# Backward-compatible entry point used by older deployment scripts.
seed_fixtures = seed_tournament_data


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    seeded = seed_tournament_data()
    for table_name, count in seeded.items():
        LOGGER.info("UPSERT %s: %d rows", table_name, count)
    print(f"Tournament data UPSERT completed: {sum(seeded.values())} rows in poker.db")
