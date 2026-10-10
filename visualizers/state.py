"""Language-independent state passed from traces to visualizer views."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ArrayRange:
    """An inclusive, labelled range in an array."""

    start: int
    end: int
    label: str
    style: str


@dataclass(frozen=True)
class ArrayState:
    """One immutable frame in an array algorithm visualization."""

    values: tuple[Any, ...]
    pointers: tuple[tuple[str, int], ...] = ()
    ranges: tuple[ArrayRange, ...] = ()
    highlights: frozenset[int] = frozenset()
    message: str = ""
