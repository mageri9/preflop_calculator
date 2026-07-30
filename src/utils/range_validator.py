"""Validation helpers for compact poker preflop range notation."""

from __future__ import annotations

import re


RANKS = "23456789TJQKA"
_PAIR_RE = re.compile(r"^([2-9TJQKA])\1\+?$")
_PAIR_INTERVAL_RE = re.compile(r"^([2-9TJQKA])\1-([2-9TJQKA])\2$")
_NON_PAIR_RE = re.compile(r"^([2-9TJQKA])([2-9TJQKA])[so]\+?$")


def _is_valid_token(token: str) -> bool:
    """Return whether one comma-delimited range token is valid."""
    pair_match = _PAIR_RE.fullmatch(token)
    if pair_match:
        return True

    interval_match = _PAIR_INTERVAL_RE.fullmatch(token)
    if interval_match:
        # Poker pair intervals are written from the higher pair to the lower.
        return RANKS.index(interval_match.group(1)) > RANKS.index(interval_match.group(2))

    non_pair_match = _NON_PAIR_RE.fullmatch(token)
    if non_pair_match:
        return RANKS.index(non_pair_match.group(1)) > RANKS.index(non_pair_match.group(2))

    return False


def _invalid_token(range_str: str) -> str | None:
    """Return the first invalid token, or ``None`` for a valid range."""
    if not isinstance(range_str, str) or not range_str.strip():
        return range_str if isinstance(range_str, str) else str(range_str)

    for raw_token in range_str.split(","):
        token = raw_token.strip()
        if not token or not _is_valid_token(token):
            return token
    return None


def validate_range_str(range_str: str) -> bool:
    """Validate a comma-separated poker range without raising an exception."""
    return _invalid_token(range_str) is None


def validate_range_str_raise(range_str: str) -> None:
    """Validate a range, raising ``ValueError`` with its first bad token."""
    token = _invalid_token(range_str)
    if token is not None:
        raise ValueError(f"Некорректный токен диапазона: {token}")
