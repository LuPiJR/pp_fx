"""Opaque application handle for an adapter-owned request-scoped table."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TableHandle:
    """Nominal lookup token; it contains no pandas object or table operations."""

    token: str

    def __post_init__(self) -> None:
        if not self.token or self.token != self.token.strip() or any(
            character.isspace() for character in self.token
        ):
            raise ValueError("A table handle token must be non-empty and whitespace-free.")
