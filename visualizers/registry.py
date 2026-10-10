"""Map locally tracked LeetCode slugs to optional visualizer traces."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from .state import ArrayState
from .traces.arrays import trace_move_zeroes, trace_sort_colors


TraceFunction = Callable[[list[int]], Iterable[ArrayState]]


@dataclass(frozen=True)
class ArrayVisualizerSpec:
    """Configuration needed to run an array visualizer with custom input."""

    title: str
    default_values: tuple[int, ...]
    trace: TraceFunction


VISUALIZERS: dict[str, ArrayVisualizerSpec] = {
    "sort_colors": ArrayVisualizerSpec(
        title="Sort Colors — Dutch National Flag",
        default_values=(2, 0, 2, 1, 1, 0),
        trace=trace_sort_colors,
    ),
    "move_zeroes": ArrayVisualizerSpec(
        title="Move Zeroes — Slow/Fast Pointers",
        default_values=(0, 1, 0, 3, 12),
        trace=trace_move_zeroes,
    ),
}


def get_visualizer(slug: str) -> ArrayVisualizerSpec | None:
    """Return the visualizer registered for a problem slug."""
    return VISUALIZERS.get(slug)
