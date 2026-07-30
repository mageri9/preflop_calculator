"""Algorithmic flop-texture and hero-hand classification utilities."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import TypeAlias


CardsInput: TypeAlias = list[str] | str

RANKS = "23456789TJQKA"
SUITS = frozenset("shdc")
RANK_VALUES = {rank: value for value, rank in enumerate(RANKS)}


@dataclass(frozen=True, slots=True)
class Card:
    """A playing card, with ranks represented from deuce (0) through ace (12)."""

    rank: int
    suit: str


def parse_cards(cards_input: CardsInput) -> list[Card]:
    """Parse compact card notation such as ``'Kc7d2h'`` into card objects."""
    if isinstance(cards_input, str):
        if len(cards_input) % 2:
            raise ValueError("Card string must contain two characters per card")
        tokens = [cards_input[index : index + 2] for index in range(0, len(cards_input), 2)]
    elif isinstance(cards_input, list) and all(isinstance(card, str) for card in cards_input):
        tokens = cards_input
    else:
        raise ValueError("Cards must be a string or a list of card strings")

    result: list[Card] = []
    for token in tokens:
        if len(token) != 2:
            raise ValueError(f"Invalid card notation: {token!r}")
        rank, suit = token[0].upper(), token[1].lower()
        if rank not in RANK_VALUES or suit not in SUITS:
            raise ValueError(f"Invalid card notation: {token!r}")
        result.append(Card(rank=RANK_VALUES[rank], suit=suit))
    return result


def _validate_cards(cards: list[Card], expected_count: int, label: str) -> None:
    if len(cards) != expected_count:
        raise ValueError(f"{label} must contain exactly {expected_count} cards")
    if len(set(cards)) != len(cards):
        raise ValueError("Duplicate cards are not allowed")


def _is_drawy_board(cards: list[Card]) -> bool:
    ranks = sorted({card.rank for card in cards})
    return len(ranks) >= 2 and any(right - left <= 2 for left, right in zip(ranks, ranks[1:]))


def classify_flop_texture(flop_input: CardsInput) -> str:
    """Return the strategy texture identifier for a validated three-card flop."""
    flop = parse_cards(flop_input)
    _validate_cards(flop, 3, "Flop")
    suit_counts = Counter(card.suit for card in flop)
    rank_counts = Counter(card.rank for card in flop)
    ranks = sorted(rank_counts)

    if len(suit_counts) == 1:
        return "MONOTONE"
    if max(rank_counts.values()) >= 2:
        return "PAIRED"

    high_ranks = [rank for rank in ranks if rank >= RANK_VALUES["T"]]
    three_connected = len(ranks) == 3 and ranks[-1] - ranks[0] <= 3
    high_connected = len(high_ranks) >= 2 and high_ranks[-1] - high_ranks[0] <= 2
    if three_connected or high_connected:
        return "HIGH_CONNECTED"
    if max(suit_counts.values()) == 2 and _is_drawy_board(flop):
        return "WET_TWO_TONE"
    return "DRY_RAINBOW"


def _straight_missing_ranks(cards: list[Card]) -> set[int]:
    """Return ranks that complete a straight when exactly four are already present."""
    ranks = {card.rank for card in cards}
    missing: set[int] = set()
    # Ace is also usable below a deuce in the wheel.
    patterns = [set(range(start, start + 5)) for start in range(0, 9)]
    patterns.append({12, 0, 1, 2, 3})
    for pattern in patterns:
        absent = pattern - ranks
        if len(absent) == 1 and len(pattern & ranks) == 4:
            missing.update(absent)
    return missing


def _has_straight(cards: list[Card]) -> bool:
    ranks = {card.rank for card in cards}
    return any(len(pattern & ranks) == 5 for pattern in [
        set(range(start, start + 5)) for start in range(0, 9)
    ] + [{12, 0, 1, 2, 3}])


def classify_hand_bucket(hero_input: CardsInput, flop_input: CardsInput) -> str:
    """Classify hero's current hand, applying the documented bucket priority."""
    hero = parse_cards(hero_input)
    flop = parse_cards(flop_input)
    _validate_cards(hero, 2, "Hero")
    _validate_cards(flop, 3, "Flop")
    cards = hero + flop
    if len(set(cards)) != 5:
        raise ValueError("Hero and flop cards must be unique")

    rank_counts = Counter(card.rank for card in cards)
    suit_counts = Counter(card.suit for card in cards)
    pair_count = sum(count >= 2 for count in rank_counts.values())
    if max(rank_counts.values()) >= 3 or pair_count >= 2 or _has_straight(cards) or max(suit_counts.values()) >= 5:
        return "MONSTER"

    flop_ranks = [card.rank for card in flop]
    top_rank = max(flop_ranks)
    hero_ranks = [card.rank for card in hero]
    pocket_pair = hero_ranks[0] == hero_ranks[1]
    top_pair_cards = [card for card in hero if card.rank == top_rank]
    if pocket_pair and hero_ranks[0] > top_rank:
        return "TPTK"
    if top_pair_cards:
        kicker = next(card.rank for card in hero if card.rank != top_rank)
        if kicker == RANK_VALUES["A"]:
            return "TPTK"
        if kicker >= RANK_VALUES["T"]:
            return "TPGK"
        return "WEAK_PAIR"
    if pocket_pair or any(card.rank in flop_ranks for card in hero):
        return "WEAK_PAIR"

    flush_draw_suit = next((suit for suit, count in suit_counts.items() if count == 4), None)
    straight_missing = _straight_missing_ranks(cards)
    has_flush_draw = flush_draw_suit is not None
    has_straight_draw = bool(straight_missing)
    has_nut_flush_draw = has_flush_draw and any(
        card.rank == RANK_VALUES["A"] and card.suit == flush_draw_suit for card in hero
    )
    if has_nut_flush_draw or (has_flush_draw and has_straight_draw) or len(straight_missing) >= 2:
        return "NUT_DRAW"
    if has_straight_draw or all(rank > top_rank for rank in hero_ranks):
        return "GUTSHOT"
    return "AIR"


def evaluate_postflop(hero_input: CardsInput, flop_input: CardsInput) -> dict[str, str]:
    """Evaluate the public flop texture and hero hand-bucket identifiers."""
    return {
        "texture_id": classify_flop_texture(flop_input),
        "bucket_id": classify_hand_bucket(hero_input, flop_input),
    }
