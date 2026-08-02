"""Shared preflop position and dead-money helpers."""

POSITIONS_BY_SIZE: dict[int, tuple[str, ...]] = {
    2: ("BTN/SB", "BB"), 3: ("BTN", "SB", "BB"),
    4: ("CO", "BTN", "SB", "BB"), 5: ("UTG", "CO", "BTN", "SB", "BB"),
    6: ("UTG", "HJ", "CO", "BTN", "SB", "BB"),
    7: ("UTG", "MP", "HJ", "CO", "BTN", "SB", "BB"),
    8: ("UTG", "MP", "MP+1", "HJ", "CO", "BTN", "SB", "BB"),
    9: ("UTG", "UTG+1", "MP", "MP+1", "HJ", "CO", "BTN", "SB", "BB"),
}


def position_risk(table_size: int, position: str) -> float:
    positions = POSITIONS_BY_SIZE[max(2, min(9, table_size))]
    normalized = position.strip().upper()
    if normalized not in positions:
        return 0.5
    return positions.index(normalized) / max(1, len(positions) - 1)


def blinds_and_antes_bb(table_size: int, has_ante: bool) -> float:
    players = max(2, min(9, table_size))
    return 1.5 + (players * 0.125 if has_ante else 0.0)
