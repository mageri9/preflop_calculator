import pytest

from src.engine.postflop_evaluator import (
    Card,
    classify_flop_texture,
    classify_hand_bucket,
    parse_cards,
    resolve_hero_cards,
)


@pytest.mark.parametrize("cards_input", ["Kc7d2h", ["Kc", "7d", "2h"]])
def test_parse_cards(cards_input: list[str] | str) -> None:
    assert parse_cards(cards_input) == [Card(11, "c"), Card(5, "d"), Card(0, "h")]


def test_duplicate_cards_raise_value_error() -> None:
    with pytest.raises(ValueError, match="unique"):
        classify_hand_bucket("KsKh", "Ks7d2h")


@pytest.mark.parametrize(
    ("flop", "texture"),
    [("Kh7h2h", "MONOTONE"), ("KcKd2h", "PAIRED"), ("Kc7d2h", "DRY_RAINBOW")],
)
def test_classify_flop_texture(flop: str, texture: str) -> None:
    assert classify_flop_texture(flop) == texture


def test_set_is_monster() -> None:
    assert classify_hand_bucket("7s7c", "7dKh2c") == "MONSTER"


def test_overpair_is_tptk() -> None:
    assert classify_hand_bucket("AsAh", "Kc7d2h") == "TPTK"


def test_nut_flush_draw_and_top_pair_priority() -> None:
    assert classify_hand_bucket("AhKh", "Qh7h2c") == "NUT_DRAW"
    assert classify_hand_bucket("AhKd", "Kh7h2c") == "TPTK"


def test_matrix_combo_is_resolved_around_blocked_flop_cards() -> None:
    hero = resolve_hero_cards("AKo", ["Ks", "7d", "2c"])
    assert len(hero) == 2
    assert hero[0].rank != hero[1].rank
    assert hero[0].suit != hero[1].suit
    assert classify_hand_bucket("AKo", ["Ks", "7d", "2c"]) == "TPTK"
