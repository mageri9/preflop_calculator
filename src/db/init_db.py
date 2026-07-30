"""Create the database schema and insert reference data."""

from sqlalchemy.dialects.sqlite import insert

from .base import Base, SessionLocal, engine
from .models import FlopTexture, HandBucket, PositionLabel


POSITION_LABELS: dict[int, tuple[str, ...]] = {
    9: ("BTN", "SB", "BB", "UTG", "UTG+1", "MP", "MP+1", "HJ", "CO"),
    8: ("BTN", "SB", "BB", "UTG", "MP", "MP+1", "HJ", "CO"),
    6: ("BTN", "SB", "BB", "UTG", "HJ", "CO"),
    2: ("BTN/SB", "BB"),
}

FLOP_TEXTURES: tuple[dict[str, str], ...] = (
    {"texture_id": "DRY_RAINBOW", "description": "Dry rainbow board with few draws."},
    {"texture_id": "WET_TWO_TONE", "description": "Connected two-tone board with draws."},
    {"texture_id": "MONOTONE", "description": "Three cards of the same suit."},
    {"texture_id": "PAIRED", "description": "Board containing a paired rank."},
    {"texture_id": "HIGH_CONNECTED", "description": "High, connected board texture."},
)

HAND_BUCKETS: tuple[dict[str, str], ...] = (
    {"bucket_id": "MONSTER", "description": "Sets, two pair, and very strong made hands."},
    {"bucket_id": "TPTK", "description": "Top pair with top kicker."},
    {"bucket_id": "TPGK", "description": "Top pair with good kicker."},
    {"bucket_id": "WEAK_PAIR", "description": "Weak top pair, middle pair, or bottom pair."},
    {"bucket_id": "NUT_DRAW", "description": "Nut flush draw, open-ended draw, or combo draw."},
    {"bucket_id": "GUTSHOT", "description": "Inside straight draw."},
    {"bucket_id": "AIR", "description": "No made hand and no meaningful draw."},
)


def _seed_defaults() -> None:
    """Insert reference rows without replacing user-managed strategy data."""
    position_rows = [
        {"table_size": size, "seat_index": seat, "label": label}
        for size, labels in POSITION_LABELS.items()
        for seat, label in enumerate(labels)
    ]
    with SessionLocal() as session:
        with session.begin():
            session.execute(insert(PositionLabel).values(position_rows).on_conflict_do_nothing())
            session.execute(insert(FlopTexture).values(FLOP_TEXTURES).on_conflict_do_nothing())
            session.execute(insert(HandBucket).values(HAND_BUCKETS).on_conflict_do_nothing())


def init_db() -> None:
    """Create all tables and seed the static reference data."""
    Base.metadata.create_all(bind=engine)
    _seed_defaults()


if __name__ == "__main__":
    init_db()
    print("Database initialized: poker.db")
