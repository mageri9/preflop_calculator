"""Validate and load JSON fixture data into the local SQLite database."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from sqlalchemy.dialects.sqlite import insert

from src.utils.range_validator import validate_range_str_raise

from .base import Base, SessionLocal, engine
from .models import (
    BlindStructure,
    FacingActionRange,
    IcmPushFold,
    NashPushFold,
    OpenRange,
    PostflopStrategy,
)


LOGGER = logging.getLogger(__name__)
FIXTURES_DIR = Path(__file__).resolve().parents[2] / "data" / "fixtures"
_MODEL_BY_FIXTURE = {
    "open_ranges.json": OpenRange,
    "nash_pushfold.json": NashPushFold,
    "icm_pushfold.json": IcmPushFold,
    "facing_action_ranges.json": FacingActionRange,
    "blind_structures.json": BlindStructure,
    "postflop_strategies.json": PostflopStrategy,
}


def _read_fixture(path: Path) -> list[dict[str, Any]]:
    """Read one fixture and verify its top-level JSON structure."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Не удалось прочитать фикстуру {path}: {exc}") from exc

    if not isinstance(payload, list) or not all(isinstance(row, dict) for row in payload):
        raise ValueError(f"Фикстура {path} должна содержать JSON-массив объектов")
    return payload


def _validate_ranges(rows: list[dict[str, Any]], path: Path) -> None:
    """Validate every range field before its fixture can modify the database."""
    for row_index, row in enumerate(rows, start=1):
        for field_name, value in row.items():
            if field_name.startswith("range_") and value is not None:
                try:
                    validate_range_str_raise(value)
                except ValueError as exc:
                    raise ValueError(f"{path.name}, запись {row_index}, поле {field_name}: {exc}") from exc


def _upsert_rows(model: type[Any], rows: list[dict[str, Any]]) -> None:
    """Insert fixture rows or replace their non-primary-key values on conflict."""
    if not rows:
        return
    table = model.__table__
    statement = insert(table).values(rows)
    update_values = {
        column.name: statement.excluded[column.name]
        for column in table.columns
        if not column.primary_key
    }
    statement = statement.on_conflict_do_update(
        index_elements=list(table.primary_key.columns), set_=update_values
    )
    with SessionLocal() as session:
        with session.begin():
            session.execute(statement)


def seed_fixtures() -> None:
    """Validate all known JSON fixtures and UPSERT them into ``poker.db``."""
    if not FIXTURES_DIR.is_dir():
        raise FileNotFoundError(f"Папка с фикстурами не найдена: {FIXTURES_DIR}")

    Base.metadata.create_all(bind=engine)
    for path in sorted(FIXTURES_DIR.glob("*.json")):
        model = _MODEL_BY_FIXTURE.get(path.name)
        if model is None:
            LOGGER.warning("Пропущена неизвестная фикстура: %s", path)
            continue
        rows = _read_fixture(path)
        _validate_ranges(rows, path)
        _upsert_rows(model, rows)
        LOGGER.info("Импортировано %d записей из %s", len(rows), path.name)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        seed_fixtures()
    except (OSError, ValueError) as exc:
        LOGGER.error("Импорт фикстур завершился с ошибкой: %s", exc)
        raise SystemExit(1) from exc
    print("Фикстуры импортированы в poker.db")
